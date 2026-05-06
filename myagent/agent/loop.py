"""Minimal agent loop for processing messages from the bus."""

import asyncio
import json

from myagent.bus import InboundMessage, MessageBus, OutboundMessage
from myagent.agent.context import ContextBuilder, Message
from myagent.providers import BaseProvider, create_provider
from myagent.providers.base import ProviderResponse, ToolCall
from myagent.tools import ToolRegistry, create_default_registry

MAX_TOOL_ITERATIONS = 3


class AgentLoop:
    """Consume inbound messages, ask a provider, and publish outbound replies."""

    def __init__(
        self,
        bus: MessageBus,
        provider: BaseProvider | None = None,
        context_builder: ContextBuilder | None = None,
        tool_registry: ToolRegistry | None = None,
        max_tool_iterations: int = MAX_TOOL_ITERATIONS,
    ) -> None:
        self.bus = bus
        self.provider = provider or create_provider()
        self.context_builder = context_builder or ContextBuilder()
        self.tool_registry = tool_registry or create_default_registry()
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
        history = self._history_for(inbound.session_key)
        messages = self.context_builder.build_messages(inbound, history)
        try:
            content = await self._generate_with_tools(messages, inbound)
        except Exception as exc:
            content = f"Error: {exc}"
        outbound = OutboundMessage(
            channel=inbound.channel,
            chat_id=inbound.chat_id,
            content=content,
        )
        await self.bus.publish_outbound(outbound)
        history.extend(
            [
                {"role": "user", "content": inbound.content},
                {"role": "assistant", "content": content},
            ]
        )
        return outbound

    async def _generate_with_tools(self, messages: list[Message], inbound: InboundMessage) -> str:
        """Generate a response, allowing the provider to call registered tools."""
        if not hasattr(self.provider, "generate_response"):
            return await self.provider.generate(messages)

        tools = self.tool_registry.get_definitions()
        if not tools:
            return await self.provider.generate(messages)

        working_messages = list(messages)
        for _ in range(self.max_tool_iterations):
            response = await self.provider.generate_response(working_messages, tools=tools)
            if not response.tool_calls:
                return response.content

            working_messages.append(_assistant_tool_call_message(response))
            for tool_call in response.tool_calls:
                await self._publish_tool_status(inbound, tool_call)
                result = await self._execute_tool_call(tool_call)
                working_messages.append(_tool_result_message(tool_call, result))

        return "I reached the tool call limit before producing a final answer."

    async def _execute_tool_call(self, tool_call: ToolCall) -> str:
        """Run one requested tool call through the registry."""
        try:
            return await self.tool_registry.execute(tool_call.name, tool_call.arguments)
        except Exception as exc:
            return f"Error executing tool {tool_call.name}: {exc}"

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
    return f"Using tool: {tool_call.name}{suffix}"


def _format_tool_arguments(arguments: dict[str, object]) -> str:
    """Show a compact argument summary without dumping large payloads."""
    parts: list[str] = []
    for key, value in arguments.items():
        text = str(value)
        if len(text) > 60:
            text = f"{text[:57]}..."
        parts.append(f"{key}={text}")
    return " ".join(parts)
