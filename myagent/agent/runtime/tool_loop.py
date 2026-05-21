"""Provider/tool iteration for one agent turn."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from myagent.approval import (
    ApprovalRoute,
    reset_current_approval_route,
    set_current_approval_route,
)
from myagent.agent.context.types import Message
from myagent.agent.runtime.messages import assistant_tool_call_message, tool_result_message
from myagent.agent.runtime.skill_state import AgentSkillState
from myagent.agent.delegation.subagent import DelegateTaskTool
from myagent.bus import InboundMessage, MessageBus, OutboundMessage
from myagent.providers import BaseProvider
from myagent.providers.base import ToolCall
from myagent.tools import ToolRegistry

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
    attachments: list[str] = field(default_factory=list)
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
        """Return compact completion data for internal diagnostics."""
        return {
            "stop_reason": self.stop_reason or "unknown",
            "iterations": self.iteration,
            "max_iterations": self.max_iterations,
            "tool_call_count": self.tool_call_count,
            "tool_error_count": self.tool_error_count,
            "warnings": list(self.warnings),
            "warning_count": len(self.warnings),
        }


class AgentToolLoop:
    """Run bounded provider/tool iterations for a single main-agent turn."""

    def __init__(
        self,
        provider: BaseProvider,
        tool_registry: ToolRegistry,
        bus: MessageBus,
        skill_state: AgentSkillState,
        max_iterations: int,
    ) -> None:
        self.provider = provider
        self.tool_registry = tool_registry
        self.bus = bus
        self.skill_state = skill_state
        self.max_iterations = max_iterations

    async def generate(
        self,
        messages: list[Message],
        inbound: InboundMessage,
        turn_state: AgentTurnState,
    ) -> str:
        """Generate a response, allowing the provider to call registered tools."""
        tools = self.tool_registry.get_definitions()

        working_messages = list(messages)
        for iteration in range(1, self.max_iterations + 1):
            turn_state.iteration = iteration
            response = await self.provider.generate_response(working_messages, tools=tools)
            if not response.tool_calls:
                turn_state.stop_reason = "final_output"
                return response.content

            working_messages.append(assistant_tool_call_message(response))
            for tool_call in response.tool_calls:
                await self._publish_tool_status(inbound, tool_call)
                result = await self._execute_tool_call(
                    tool_call,
                    inbound.session_key,
                    turn_state.turn_id,
                    inbound.channel,
                    inbound.chat_id,
                    turn_state,
                )
                turn_state.record_tool_result(tool_call, result)
                working_messages.append(tool_result_message(tool_call, result))

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
        channel: str = "",
        chat_id: str = "",
        turn_state: AgentTurnState | None = None,
    ) -> str:
        """Run one requested tool call through the registry."""
        try:
            route_token = set_current_approval_route(ApprovalRoute(channel, chat_id))
            try:
                result = await self._execute_tool(
                    tool_call,
                    session_key,
                    turn_id,
                    channel,
                    chat_id,
                    turn_state,
                )
            finally:
                reset_current_approval_route(route_token)
        except Exception as exc:
            result = f"Error executing tool {tool_call.name}: {exc}"
        return result

    async def _execute_tool(
        self,
        tool_call: ToolCall,
        session_key: str,
        turn_id: str,
        channel: str = "",
        chat_id: str = "",
        turn_state: AgentTurnState | None = None,
    ) -> str:
        """Run one tool, adding runtime context for special tools when needed."""
        arguments = self._tool_arguments(tool_call, channel, chat_id, turn_state)

        tool = self.tool_registry.get(tool_call.name)
        if not isinstance(tool, DelegateTaskTool):
            return await self.tool_registry.execute(tool_call.name, arguments)

        casted = tool.cast_params(arguments)
        errors = tool.validate_params(casted)
        if errors:
            return (
                f"Error: Invalid parameters for tool '{tool_call.name}': "
                + "; ".join(errors)
            )

        return await tool.execute(
            **casted,
            active_skill_context=self.skill_state.format_active_skill_context(
                session_key,
                turn_id,
            ),
        )

    def _tool_arguments(
        self,
        tool_call: ToolCall,
        channel: str,
        chat_id: str,
        turn_state: AgentTurnState | None,
    ) -> dict[str, object]:
        arguments = dict(tool_call.arguments)
        if tool_call.name == "cron" and channel:
            arguments["_channel"] = channel
            arguments["_chat_id"] = chat_id
        if tool_call.name == "attach_file" and turn_state is not None:
            arguments["_attachments"] = turn_state.attachments
        return arguments

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
