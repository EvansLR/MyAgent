"""Minimal agent loop for processing messages from the bus."""

import asyncio
import json
from uuid import uuid4

from myagent.bus import InboundMessage, MessageBus, OutboundMessage
from myagent.agent.context import ContextBuilder, Message
from myagent.agent.subagent import DelegateTaskTool
from myagent.memory import JsonlMemoryStore, MarkdownMemoryStore, MemoryExtractor
from myagent.providers import BaseProvider, create_provider
from myagent.providers.base import ProviderResponse, ToolCall
from myagent.skills import SkillRegistry
from myagent.tools import (
    MemoryAppendDailyTool,
    MemoryForgetTool,
    MemoryGetTool,
    MemoryProposeLongTermTool,
    MemorySearchTool,
    ToolRegistry,
    create_default_registry,
)
from myagent.tracing import JsonlTraceStore, TraceStore

MAX_TOOL_ITERATIONS = 8


class AgentLoop:
    """Consume inbound messages, ask a provider, and publish outbound replies."""

    def __init__(
        self,
        bus: MessageBus,
        provider: BaseProvider | None = None,
        context_builder: ContextBuilder | None = None,
        tool_registry: ToolRegistry | None = None,
        trace_store: TraceStore | None = None,
        memory_store: JsonlMemoryStore | None = None,
        markdown_memory_store: MarkdownMemoryStore | None = None,
        memory_extractor: MemoryExtractor | None = None,
        skill_registry: SkillRegistry | None = None,
        max_tool_iterations: int = MAX_TOOL_ITERATIONS,
    ) -> None:
        self.bus = bus
        self.provider = provider or create_provider()
        self.memory_store = memory_store or JsonlMemoryStore()
        self.markdown_memory_store = markdown_memory_store or MarkdownMemoryStore()
        self.memory_extractor = memory_extractor or MemoryExtractor(
            self.provider,
            self.markdown_memory_store,
        )
        self.skill_registry = skill_registry or SkillRegistry.from_directory()
        self.context_builder = context_builder or ContextBuilder(
            core_memory_provider=self.markdown_memory_store.read_core_memory,
            skill_registry=self.skill_registry,
        )
        self.tool_registry = tool_registry or create_default_registry()
        self._register_memory_tools()
        if not self.tool_registry.has("delegate_task"):
            self.tool_registry.register(DelegateTaskTool(self.provider, self.tool_registry))
        self.trace_store = trace_store or JsonlTraceStore()
        self.max_tool_iterations = max_tool_iterations
        self._history: dict[str, list[Message]] = {}
        self._lock = asyncio.Lock()
        self._running = False

    @property
    def running(self) -> bool:
        """Return whether the loop should keep processing messages."""
        return self._running

    @property
    def locked(self) -> bool:
        """Return whether a turn is currently being processed."""
        return self._lock.locked()

    async def process_next(self) -> OutboundMessage:
        """Process one inbound message and publish one outbound message."""
        inbound = await self.bus.consume_inbound()
        async with self._lock:
            return await self.process_message(inbound)

    async def process_message(self, inbound: InboundMessage) -> OutboundMessage:
        """Generate and publish an outbound response for one inbound message."""
        turn_id = uuid4().hex
        self._trace(
            inbound.session_key,
            turn_id,
            "user_message",
            {
                "channel": inbound.channel,
                "chat_id": inbound.chat_id,
                "content": inbound.content,
            },
        )
        history = self._history_for(inbound.session_key)
        messages, context_report = self.context_builder.build_messages_with_report(
            inbound,
            history,
        )
        self.context_builder.last_report = context_report
        self._trace(
            inbound.session_key,
            turn_id,
            "context_built",
            {
                "message_count": len(messages),
                "roles": [message.get("role") for message in messages],
                "context": context_report.to_dict(),
            },
        )
        try:
            content = await self._generate_with_tools(messages, inbound, turn_id)
        except Exception as exc:
            content = f"Error: {exc}"
            self._trace(
                inbound.session_key,
                turn_id,
                "error",
                {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            )
        outbound = OutboundMessage(
            channel=inbound.channel,
            chat_id=inbound.chat_id,
            content=content,
        )
        self._trace(
            inbound.session_key,
            turn_id,
            "final_answer",
            {
                "content_preview": _preview(content),
                "content_length": len(content),
            },
        )
        await self.bus.publish_outbound(outbound)
        await self._extract_memory_after_turn(inbound, content, turn_id)
        history.extend(
            [
                {"role": "user", "content": inbound.content},
                {"role": "assistant", "content": content},
            ]
        )
        return outbound

    async def _generate_with_tools(
        self,
        messages: list[Message],
        inbound: InboundMessage,
        turn_id: str,
    ) -> str:
        """Generate a response, allowing the provider to call registered tools."""
        if not hasattr(self.provider, "generate_response"):
            self._trace_llm_request(inbound.session_key, turn_id, 1, len(messages), 0)
            return await self.provider.generate(messages)

        tools = self.tool_registry.get_definitions()
        if not tools:
            self._trace_llm_request(inbound.session_key, turn_id, 1, len(messages), 0)
            return await self.provider.generate(messages)

        working_messages = list(messages)
        for iteration in range(1, self.max_tool_iterations + 1):
            self._trace_llm_request(
                inbound.session_key,
                turn_id,
                iteration,
                len(working_messages),
                len(tools),
            )
            response = await self.provider.generate_response(working_messages, tools=tools)
            self._trace(
                inbound.session_key,
                turn_id,
                "llm_response",
                {
                    "iteration": iteration,
                    "content_preview": _preview(response.content),
                    "tool_call_count": len(response.tool_calls),
                    "tool_names": [tool_call.name for tool_call in response.tool_calls],
                },
            )
            if not response.tool_calls:
                return response.content

            working_messages.append(_assistant_tool_call_message(response))
            for tool_call in response.tool_calls:
                await self._publish_tool_status(inbound, tool_call)
                result = await self._execute_tool_call(tool_call, inbound.session_key, turn_id)
                working_messages.append(_tool_result_message(tool_call, result))

        return "工具调用次数已达到上限，暂时还没有生成最终回答。"

    async def _execute_tool_call(
        self,
        tool_call: ToolCall,
        session_key: str,
        turn_id: str,
    ) -> str:
        """Run one requested tool call through the registry."""
        self._trace(
            session_key,
            turn_id,
            "tool_call",
            {
                "tool_call_id": tool_call.id,
                "tool_name": tool_call.name,
                "arguments": tool_call.arguments,
            },
        )
        if tool_call.name == "delegate_task":
            self._trace(
                session_key,
                turn_id,
                "subagent_start",
                {
                    "tool_call_id": tool_call.id,
                    "agent_type": tool_call.arguments.get("agent_type", "researcher"),
                    "task_preview": _preview(str(tool_call.arguments.get("task", ""))),
                },
            )
        try:
            result = await self.tool_registry.execute(tool_call.name, tool_call.arguments)
        except Exception as exc:
            result = f"Error executing tool {tool_call.name}: {exc}"
        if tool_call.name == "delegate_task":
            self._trace(
                session_key,
                turn_id,
                "subagent_result",
                {
                    "tool_call_id": tool_call.id,
                    "result_preview": _preview(result),
                    "result_length": len(result),
                },
            )
        self._trace(
            session_key,
            turn_id,
            "tool_result",
            {
                "tool_call_id": tool_call.id,
                "tool_name": tool_call.name,
                "result_preview": _preview(result),
                "result_length": len(result),
            },
        )
        return result

    async def _publish_tool_status(self, inbound: InboundMessage, tool_call: ToolCall) -> None:
        """Publish a user-visible status message before running a tool."""
        await self.bus.publish_outbound(
            OutboundMessage(
                channel=inbound.channel,
                chat_id=inbound.chat_id,
                content=_format_tool_status(tool_call),
                metadata={
                    "kind": "status",
                    "tool_name": tool_call.name,
                    "tool_call_id": tool_call.id,
                },
            )
        )

    async def run_until_stopped(self) -> None:
        """Keep processing messages until stopped or cancelled."""
        self._running = True
        while self._running:
            await self.process_next()

    def stop(self) -> None:
        """Request the processing loop to stop."""
        self._running = False

    def history_for(self, session_key: str) -> list[Message]:
        """Return a copy of the current session history."""
        return list(self._history_for(session_key))

    def _history_for(self, session_key: str) -> list[Message]:
        return self._history.setdefault(session_key, [])

    def _register_memory_tools(self) -> None:
        """Expose local personal memory tools to the main agent."""
        tools = (
            MemoryAppendDailyTool(self.markdown_memory_store),
            MemoryProposeLongTermTool(self.markdown_memory_store),
            MemorySearchTool(self.markdown_memory_store),
            MemoryGetTool(self.markdown_memory_store),
            MemoryForgetTool(self.markdown_memory_store),
        )
        for tool in tools:
            if not self.tool_registry.has(tool.name):
                self.tool_registry.register(tool)

    async def _extract_memory_after_turn(
        self,
        inbound: InboundMessage,
        assistant_answer: str,
        turn_id: str,
    ) -> None:
        """Run post-turn memory extraction after the final answer."""
        if self.memory_extractor is None:
            return
        try:
            memory_ids = await self.memory_extractor.extract_turn(
                inbound.content,
                assistant_answer,
            )
        except Exception as exc:
            self._trace(
                inbound.session_key,
                turn_id,
                "memory_extraction_error",
                {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            )
            return
        if memory_ids:
            self._trace(
                inbound.session_key,
                turn_id,
                "memory_candidates_saved",
                {
                    "memory_ids": memory_ids,
                    "count": len(memory_ids),
                },
            )

    def _trace(
        self,
        session_key: str,
        turn_id: str,
        event: str,
        data: dict[str, object] | None = None,
    ) -> None:
        """Record a trace event without letting trace failures affect chat."""
        try:
            self.trace_store.record(session_key, turn_id, event, data)
        except Exception:
            pass

    def _trace_llm_request(
        self,
        session_key: str,
        turn_id: str,
        iteration: int,
        message_count: int,
        tool_count: int,
    ) -> None:
        """Record a compact provider request event."""
        self._trace(
            session_key,
            turn_id,
            "llm_request",
            {
                "iteration": iteration,
                "message_count": message_count,
                "tool_count": tool_count,
            },
        )


def _assistant_tool_call_message(response: ProviderResponse) -> Message:
    """Build an assistant message containing tool calls for chat completions."""
    message: Message = {
        "role": "assistant",
        "content": response.content,
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.name,
                    "arguments": json.dumps(tool_call.arguments, ensure_ascii=False),
                },
            }
            for tool_call in response.tool_calls
        ],
    }
    message.update(response.extra_message_fields)
    return message


def _tool_result_message(tool_call: ToolCall, result: str) -> Message:
    """Build a tool result message for chat completions."""
    return {
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": result,
    }


def _format_tool_status(tool_call: ToolCall) -> str:
    """Build a short human-readable status line for a tool call."""
    args = _format_tool_arguments(tool_call.arguments)
    suffix = f" {args}" if args else ""
    return f"正在调用工具：{tool_call.name}{suffix}"


def _format_tool_arguments(arguments: dict[str, object]) -> str:
    """Show a compact argument summary without dumping large payloads."""
    parts: list[str] = []
    for key, value in arguments.items():
        text = str(value)
        if len(text) > 60:
            text = f"{text[:57]}..."
        parts.append(f"{key}={text}")
    return " ".join(parts)


def _preview(text: str, limit: int = 300) -> str:
    """Return a compact single-line preview for trace files."""
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."
