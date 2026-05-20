"""Minimal agent loop for processing messages from the bus."""

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from myagent.approval import (
    ApprovalRoute,
    reset_current_approval_route,
    set_current_approval_route,
)
from myagent.bus import InboundMessage, MessageBus, OutboundMessage
from myagent.agent.context import ContextBuilder
from myagent.agent.context_types import Message
from myagent.agent.runtime_env import format_runtime_environment
from myagent.agent.summary import (
    ConversationSummarizer,
    ConversationSummaryConfig,
)
from myagent.agent.run_events import AgentRunEvents
from myagent.agent.session_history import AgentSessionHistory
from myagent.agent.subagent import DelegateTaskTool
from myagent.cron.types import CronJob
from myagent.memory import MarkdownMemoryStore, MemoryConsolidator
from myagent.memory.extractor import MemoryExtractor
from myagent.providers import BaseProvider, create_provider
from myagent.providers.base import ProviderResponse, ToolCall
from myagent.skills import SkillRegistry
from myagent.tools import (
    MemoryArchiveTool,
    MemoryForgetTool,
    MemoryGetTool,
    MemoryProposeTool,
    MemoryRememberTool,
    MemorySearchTool,
    SkillGetTool,
    ToolRegistry,
    create_default_registry,
)
from myagent.tracing import JsonlTraceStore, TraceStore
from myagent.profile import ProfileLoader

if TYPE_CHECKING:
    from myagent.cron.service import CronService

MAX_TOOL_ITERATIONS = 50
MAX_REPEATED_TOOL_CALLS = 2


@dataclass(slots=True)
class AgentTurnState:
    """Small observable state object for one AgentLoop turn."""

    session_key: str
    turn_id: str
    max_iterations: int
    iteration: int = 0
    tool_call_count: int = 0
    tool_error_count: int = 0
    stop_reason: str = ""
    warnings: list[str] = field(default_factory=list)
    _tool_call_counts: dict[str, int] = field(default_factory=dict)

    def record_tool_result(self, tool_call: ToolCall, result: str) -> None:
        self.tool_call_count += 1
        if result.startswith("Error"):
            self.tool_error_count += 1
        signature = _tool_call_signature(tool_call)
        self._tool_call_counts[signature] = self._tool_call_counts.get(signature, 0) + 1
        if self._tool_call_counts[signature] == MAX_REPEATED_TOOL_CALLS + 1:
            self.warnings.append(f"repeated_tool_call:{tool_call.name}")

    def to_completion_data(self) -> dict[str, object]:
        """Return trace data for the end of the turn."""
        return {
            "stop_reason": self.stop_reason or "unknown",
            "iterations": self.iteration,
            "max_iterations": self.max_iterations,
            "tool_call_count": self.tool_call_count,
            "tool_error_count": self.tool_error_count,
            "warnings": list(self.warnings),
            "warning_count": len(self.warnings),
        }


class AgentLoop:
    """Consume inbound messages, ask a provider, and publish outbound replies."""

    def __init__(
        self,
        bus: MessageBus,
        provider: BaseProvider | None = None,
        context_builder: ContextBuilder | None = None,
        tool_registry: ToolRegistry | None = None,
        trace_store: TraceStore | None = None,
        markdown_memory_store: MarkdownMemoryStore | None = None,
        memory_extractor: MemoryExtractor | None = None,
        skill_registry: SkillRegistry | None = None,
        workspace_root: Path | str | None = None,
        profile_loader: ProfileLoader | None = None,
        max_tool_iterations: int = MAX_TOOL_ITERATIONS,
        conversation_summary_config: ConversationSummaryConfig | None = None,
        cron_service: "CronService | None" = None,
        start_cron: bool = True,
    ) -> None:
        self.bus = bus
        self.provider = provider or create_provider()
        self.markdown_memory_store = markdown_memory_store or MarkdownMemoryStore()
        self.memory_extractor = memory_extractor or MemoryExtractor(
            self.provider,
            self.markdown_memory_store,
        )
        self.memory_consolidator = MemoryConsolidator(
            self.provider,
            self.markdown_memory_store,
        )
        self.skill_registry = skill_registry or SkillRegistry.from_directory()
        self.profile_loader = profile_loader or ProfileLoader()
        self.conversation_summary_config = (
            conversation_summary_config or ConversationSummaryConfig()
        )
        self.conversation_summarizer = ConversationSummarizer(
            self.provider,
            self.conversation_summary_config,
        )
        self.trace_store = trace_store or JsonlTraceStore()
        self.events = AgentRunEvents(self.trace_store)
        self.session_history = AgentSessionHistory(
            self.conversation_summarizer,
            self.conversation_summary_config,
            self.memory_extractor,
            self.events,
        )
        self.context_builder = context_builder or ContextBuilder(
            runtime_environment_provider=lambda: format_runtime_environment(workspace_root),
            always_memory_provider=self.markdown_memory_store.read_always_memory,
            now_memory_provider=self.markdown_memory_store.read_now_memory,
            conversation_summary_provider=self.session_history.current_summary_context,
            active_skills_provider=self._current_active_skills_context,
            skill_registry=self.skill_registry,
            profile_provider=self.profile_loader,
        )
        if self.context_builder.conversation_summary_provider is None:
            self.context_builder.conversation_summary_provider = (
                self.session_history.current_summary_context
            )
        self.conversation_summarizer.chars_per_token = (
            self.context_builder.budget.chars_per_token
        )
        self.tool_registry = tool_registry or create_default_registry()
        self._register_memory_tools()
        if not self.tool_registry.has("delegate_task"):
            self.tool_registry.register(DelegateTaskTool(self.provider, self.tool_registry))
        self.cron_service = cron_service or self._create_default_cron_service()
        self._start_cron = start_cron
        if not self.tool_registry.has("cron"):
            from myagent.tools.cron import CronTool
            self.tool_registry.register(CronTool(self.cron_service))
        if not self.tool_registry.has("message"):
            from myagent.tools.message import MessageTool
            self.tool_registry.register(MessageTool(send_callback=self.bus.publish_outbound))
        self.max_tool_iterations = max_tool_iterations
        self._active_skills_by_turn: dict[tuple[str, str], list[dict[str, object]]] = {}
        self._current_turn_key: tuple[str, str] | None = None
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
        turn_state = AgentTurnState(
            session_key=inbound.session_key,
            turn_id=turn_id,
            max_iterations=self.max_tool_iterations,
        )
        # Set message tool context so it knows where to send
        if (mt := self.tool_registry.get("message")) and hasattr(mt, "set_context"):
            mt.set_context(inbound.channel, inbound.chat_id)
            mt.start_turn()
        self.events.user_message(inbound, turn_id)
        self.events.profile_loaded(
            inbound.session_key,
            turn_id,
            self.profile_loader.to_trace_data(),
        )
        history = self.session_history.history_for(inbound.session_key)
        self.session_history.set_current_summary_session(inbound.session_key)
        await self.session_history.compact_before_context(
            inbound.session_key,
            turn_id,
            history,
            self.context_builder.budget,
        )
        visible_history = self.session_history.visible_history_for_context(
            inbound.session_key,
            history,
        )
        messages, context_report = self.context_builder.build_messages_with_report(
            inbound,
            visible_history,
        )
        self.context_builder.last_report = context_report
        self.events.context_built(
            inbound.session_key,
            turn_id,
            messages,
            len(history),
            len(visible_history),
            context_report,
        )
        self.events.context_dropped(inbound.session_key, turn_id, context_report)
        self._current_turn_key = (inbound.session_key, turn_id)
        try:
            content = await self._generate_with_tools(messages, inbound, turn_state)
        except Exception as exc:
            turn_state.stop_reason = "provider_error"
            content = f"Error: {exc}"
            self.events.error(inbound.session_key, turn_id, exc)
        # Check if message tool already sent a reply this turn
        message_sent = False
        if (mt := self.tool_registry.get("message")) and hasattr(mt, "_sent_in_turn"):
            message_sent = mt._sent_in_turn

        if not message_sent:
            if not turn_state.stop_reason:
                turn_state.stop_reason = "final_output"
            outbound = OutboundMessage(
                channel=inbound.channel,
                chat_id=inbound.chat_id,
                content=content,
            )
            self.events.final_answer(inbound.session_key, turn_id, content)
            self.events.turn_completed(
                inbound.session_key,
                turn_id,
                turn_state.to_completion_data(),
            )
            await self.bus.publish_outbound(outbound)
        else:
            # Suppress final reply to avoid duplication; still record a trace
            outbound = OutboundMessage(
                channel=inbound.channel,
                chat_id=inbound.chat_id,
                content="",
            )
            self.events.turn_completed(
                inbound.session_key,
                turn_id,
                {**turn_state.to_completion_data(), "suppressed_final_reply": True},
            )
        history.extend(
            [
                {"role": "user", "content": inbound.content},
                {"role": "assistant", "content": content},
            ]
        )
        self._active_skills_by_turn.pop((inbound.session_key, turn_id), None)
        self._current_turn_key = None
        self.session_history.clear_current_summary_session()
        return outbound

    async def _generate_with_tools(
        self,
        messages: list[Message],
        inbound: InboundMessage,
        turn_state: AgentTurnState,
    ) -> str:
        """Generate a response, allowing the provider to call registered tools."""
        if not hasattr(self.provider, "generate_response"):
            turn_state.iteration = 1
            turn_state.stop_reason = "final_output"
            self.events.llm_request(
                inbound.session_key,
                turn_state.turn_id,
                1,
                len(messages),
                0,
            )
            return await self.provider.generate(messages)

        tools = self.tool_registry.get_definitions()
        if not tools:
            turn_state.iteration = 1
            turn_state.stop_reason = "final_output"
            self.events.llm_request(
                inbound.session_key,
                turn_state.turn_id,
                1,
                len(messages),
                0,
            )
            return await self.provider.generate(messages)

        working_messages = list(messages)
        for iteration in range(1, self.max_tool_iterations + 1):
            turn_state.iteration = iteration
            self.events.llm_request(
                inbound.session_key,
                turn_state.turn_id,
                iteration,
                len(working_messages),
                len(tools),
            )
            response = await self.provider.generate_response(working_messages, tools=tools)
            self.events.llm_response(
                inbound.session_key,
                turn_state.turn_id,
                iteration,
                response,
            )
            if not response.tool_calls:
                turn_state.stop_reason = "final_output"
                return response.content

            working_messages.append(_assistant_tool_call_message(response))
            for tool_call in response.tool_calls:
                await self._publish_tool_status(inbound, tool_call)
                result = await self._execute_tool_call(
                    tool_call,
                    inbound.session_key,
                    turn_state.turn_id,
                    inbound.content,
                    inbound.channel,
                    inbound.chat_id,
                )
                turn_state.record_tool_result(tool_call, result)
                working_messages.append(_tool_result_message(tool_call, result))

        turn_state.stop_reason = "max_tool_iterations"
        return (
            "Tool call limit reached before a stable final answer was produced. "
            "Please narrow the request, or ask me to continue with one specific direction."
        )


    async def _execute_tool_call(
        self,
        tool_call: ToolCall,
        session_key: str,
        turn_id: str,
        user_content: str = "",
        channel: str = "",
        chat_id: str = "",
    ) -> str:
        """Run one requested tool call through the registry."""
        self.events.tool_call(session_key, turn_id, tool_call)
        subagent_task_id = ""
        if tool_call.name == "delegate_task":
            subagent_task_id = uuid4().hex[:8]
            inherited_active_skills = self._active_skill_ids_for_turn(session_key, turn_id)
            self.events.subagent_start(
                session_key,
                turn_id,
                tool_call,
                subagent_task_id,
                user_content,
                inherited_active_skills,
            )
        try:
            route_token = set_current_approval_route(ApprovalRoute(channel, chat_id))
            try:
                result = await self._execute_delegate_task_with_trace(
                    tool_call,
                    session_key,
                    turn_id,
                    subagent_task_id,
                    channel,
                    chat_id,
                )
            finally:
                reset_current_approval_route(route_token)
        except Exception as exc:
            result = f"Error executing tool {tool_call.name}: {exc}"
        if tool_call.name == "delegate_task":
            self.events.subagent_result(
                session_key,
                turn_id,
                tool_call,
                subagent_task_id,
                result,
            )
        self.events.tool_result(session_key, turn_id, tool_call, result)
        return result

    async def _execute_delegate_task_with_trace(
        self,
        tool_call: ToolCall,
        session_key: str,
        turn_id: str,
        subagent_task_id: str,
        channel: str = "",
        chat_id: str = "",
    ) -> str:
        """Run delegate_task with child trace events when possible."""
        if tool_call.name != "delegate_task":
            arguments = dict(tool_call.arguments)
            if tool_call.name == "cron" and channel:
                arguments["_channel"] = channel
                arguments["_chat_id"] = chat_id
            return await self.tool_registry.execute(tool_call.name, arguments)

        tool = self.tool_registry.get(tool_call.name)
        if not isinstance(tool, DelegateTaskTool):
            return await self.tool_registry.execute(tool_call.name, tool_call.arguments)

        casted = tool.cast_params(tool_call.arguments)
        errors = tool.validate_params(casted)
        if errors:
            return f"Error: Invalid parameters for tool '{tool_call.name}': " + "; ".join(errors)

        def trace_child(event: str, data: dict[str, object]) -> None:
            child_data = {
                "parent_turn_id": turn_id,
                "parent_tool_call_id": tool_call.id,
                "delegation_reason": casted.get("reason", ""),
                **data,
            }
            self.events.record(session_key, turn_id, event, child_data)

        return await tool.execute_with_trace(
            **casted,
            active_skill_context=self._format_active_skill_context(session_key, turn_id),
            trace_hook=trace_child,
            subagent_task_id=subagent_task_id,
        )

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
        if self._start_cron:
            await self.cron_service.start()
            self._register_memory_consolidation_job()
        try:
            while self._running:
                await self.process_next()
        finally:
            if self._start_cron:
                self.cron_service.stop()

    def stop(self) -> None:
        """Request the processing loop to stop."""
        self._running = False

    def _create_default_cron_service(self):
        from myagent.cron.service import CronService
        store_path = Path.home() / ".myagent" / "runtime" / "cron" / "jobs.json"
        return CronService(
            store_path=store_path,
            on_job=self._on_cron_job,
        )

    def _register_memory_consolidation_job(self) -> None:
        """Register the periodic memory consolidation system job."""
        from myagent.cron.types import CronSchedule
        for job in self.cron_service.list_jobs(include_disabled=True):
            if job.name == "memory_consolidation" and job.payload.job_type == "system":
                return
        self.cron_service.add_job(
            name="memory_consolidation",
            schedule=CronSchedule(kind="every", every=24 * 3600),
            message="consolidate memory",
            channel="",
            chat_id="",
            delete_after_run=False,
            job_type="system",
        )

    async def _on_cron_job(self, job: CronJob) -> None:
        if job.payload.job_type == "system":
            if job.name == "memory_consolidation":
                try:
                    await self.memory_consolidator.consolidate()
                except Exception:
                    pass
            return
        # Route replies back to the channel/chat that created the job.
        channel = job.payload.channel or "scheduler"
        chat_id = job.payload.chat_id or job.id
        # Wrap the payload so the LLM knows this is a scheduled trigger,
        # not a new user question.
        content = (
            f"【定时任务触发】任务名称：{job.name}\n"
            f"这是您之前设定的定时提醒，现在已到期。\n"
            f"提醒内容：{job.payload.message}\n\n"
            f"请直接执行上述提醒，生成一条消息发送给用户。"
            f"不要询问用户设置问题，也不要再次创建定时任务。"
        )
        msg = InboundMessage(
            channel=channel,
            sender_id="cron",
            chat_id=chat_id,
            content=content,
            metadata={"job_name": job.name, "source": "cron"},
            session_key_override=f"cron:{job.id}",
        )
        await self.bus.publish_inbound(msg)

    def _register_memory_tools(self) -> None:
        """Expose local personal memory tools to the main agent."""
        tools = (
            MemoryRememberTool(self.markdown_memory_store),
            MemoryProposeTool(self.markdown_memory_store),
            MemoryArchiveTool(self.markdown_memory_store),
            MemorySearchTool(self.markdown_memory_store),
            MemoryGetTool(self.markdown_memory_store),
            MemoryForgetTool(self.markdown_memory_store),
        )
        for tool in tools:
            if not self.tool_registry.has(tool.name):
                self.tool_registry.register(tool)
        if self.skill_registry.list_skills() and not self.tool_registry.has("skill_get"):
            self.tool_registry.register(SkillGetTool(self.skill_registry, trace_hook=self._trace_skill_event))

    def _trace_skill_event(self, event: str, data: dict[str, object]) -> None:
        """Record skill tool events without coupling SkillGetTool to AgentLoop state."""
        turn_id = self._current_turn_key[1] if self._current_turn_key else "skills"
        self.events.record("runtime:skills", turn_id, event, data)
        if event != "active_skill_set" or self._current_turn_key is None:
            return
        active_skills = self._active_skills_by_turn.setdefault(self._current_turn_key, [])
        skill_id = str(data.get("skill_id") or "")
        if skill_id and any(str(skill.get("skill_id") or "") == skill_id for skill in active_skills):
            return
        active_skills.append(dict(data))

    def _active_skill_ids_for_turn(self, session_key: str, turn_id: str) -> list[str]:
        """Return active skill ids recorded during this turn."""
        return [
            str(skill.get("skill_id") or "")
            for skill in self._active_skills_by_turn.get((session_key, turn_id), [])
            if skill.get("skill_id")
        ]

    def _current_active_skills_context(self) -> str:
        """Return compact active skill context for the current main-agent turn."""
        if self._current_turn_key is None:
            return ""
        session_key, turn_id = self._current_turn_key
        active_skills = self._active_skills_by_turn.get((session_key, turn_id), [])
        if not active_skills:
            return ""
        lines = []
        for skill in active_skills:
            skill_id = str(skill.get("skill_id") or "")
            if not skill_id:
                continue
            name = str(skill.get("name") or skill_id)
            reason = str(skill.get("reason") or "")
            lines.append(f"- {skill_id}: {name}")
            if reason:
                lines.append(f"  reason: {reason}")
        return "\n".join(lines)

    def _format_active_skill_context(self, session_key: str, turn_id: str) -> str:
        """Format compact parent active skill context for delegated subagents."""
        active_skills = self._active_skills_by_turn.get((session_key, turn_id), [])
        if not active_skills:
            return ""
        lines = ["# Parent Active Skills"]
        for skill in active_skills:
            skill_id = str(skill.get("skill_id") or "")
            name = str(skill.get("name") or skill_id)
            scope = str(skill.get("scope") or "turn")
            reason = str(skill.get("reason") or "")
            lines.append(f"- {skill_id} ({name}): scope={scope}; reason={reason}")
        return "\n".join(lines)

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
    return f"Calling tool: {tool_call.name}{suffix}"


def _format_tool_arguments(arguments: dict[str, object]) -> str:
    """Show a compact argument summary without dumping large payloads."""
    parts: list[str] = []
    for key, value in arguments.items():
        text = str(value)
        if len(text) > 60:
            text = f"{text[:57]}..."
        parts.append(f"{key}={text}")
    return " ".join(parts)



def _tool_call_signature(tool_call: ToolCall) -> str:
    """Return a stable signature for repeated tool-call diagnostics."""
    arguments = json.dumps(tool_call.arguments, sort_keys=True, ensure_ascii=False)
    return f"{tool_call.name}:{arguments}"
