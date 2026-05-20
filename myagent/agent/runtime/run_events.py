"""Semantic event recorder for agent runs.

The agent loop should describe the run flow. This module owns the trace payload
shape so observability does not dominate the orchestration code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from myagent.tracing.store import TraceStore

if TYPE_CHECKING:
    from myagent.agent.context.types import ContextAssemblyReport, Message
    from myagent.agent.context.summary import ConversationSummaryState
    from myagent.bus import InboundMessage
    from myagent.providers.base import ProviderResponse, ToolCall


class AgentRunEvents:
    """Record agent-run events without exposing trace formatting to AgentLoop."""

    def __init__(self, trace_store: TraceStore) -> None:
        self.trace_store = trace_store

    def record(
        self,
        session_key: str,
        turn_id: str,
        event: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Record one event, keeping trace failures out of chat behavior."""
        try:
            self.trace_store.record(session_key, turn_id, event, data)
        except Exception:
            pass

    def user_message(self, inbound: InboundMessage, turn_id: str) -> None:
        self.record(
            inbound.session_key,
            turn_id,
            "user_message",
            {
                "channel": inbound.channel,
                "chat_id": inbound.chat_id,
                "content": inbound.content,
            },
        )

    def profile_loaded(
        self,
        session_key: str,
        turn_id: str,
        profile_data: dict[str, Any],
    ) -> None:
        self.record(session_key, turn_id, "profile_loaded", profile_data)

    def context_built(
        self,
        session_key: str,
        turn_id: str,
        messages: list[Message],
        full_history_count: int,
        visible_history_count: int,
        report: ContextAssemblyReport,
    ) -> None:
        self.record(
            session_key,
            turn_id,
            "context_built",
            {
                "message_count": len(messages),
                "roles": [message.get("role") for message in messages],
                "full_history_messages": full_history_count,
                "visible_history_messages": visible_history_count,
                "context": report.to_dict(),
            },
        )

    def context_dropped(
        self,
        session_key: str,
        turn_id: str,
        report: ContextAssemblyReport,
    ) -> None:
        if not report.dropped_sections and not report.history.dropped_by_token_budget:
            return
        self.record(
            session_key,
            turn_id,
            "context_dropped",
            {
                "dropped_sections": [
                    {
                        "name": section.name,
                        "kind": section.kind,
                        "retention": section.retention,
                        "source": section.source,
                        "reason": section.reason,
                        "estimated_tokens": section.estimated_tokens,
                    }
                    for section in report.dropped_sections
                ],
                "dropped_history_messages": report.history.dropped_messages,
                "dropped_history_by_token_budget": report.history.dropped_by_token_budget,
                "estimated_tokens_before": report.estimated_tokens_before_budget,
                "estimated_tokens_after": report.estimated_tokens,
                "max_prompt_tokens": report.max_prompt_tokens,
            },
        )

    def error(self, session_key: str, turn_id: str, exc: Exception) -> None:
        self.record(
            session_key,
            turn_id,
            "error",
            {"type": type(exc).__name__, "message": str(exc)},
        )

    def final_answer(self, session_key: str, turn_id: str, content: str) -> None:
        self.record(
            session_key,
            turn_id,
            "final_answer",
            {"content_preview": preview(content), "content_length": len(content)},
        )

    def turn_completed(
        self,
        session_key: str,
        turn_id: str,
        data: dict[str, Any],
    ) -> None:
        self.record(session_key, turn_id, "turn_completed", data)

    def llm_request(
        self,
        session_key: str,
        turn_id: str,
        iteration: int,
        message_count: int,
        tool_count: int,
    ) -> None:
        self.record(
            session_key,
            turn_id,
            "llm_request",
            {
                "iteration": iteration,
                "message_count": message_count,
                "tool_count": tool_count,
            },
        )

    def llm_response(
        self,
        session_key: str,
        turn_id: str,
        iteration: int,
        response: ProviderResponse,
    ) -> None:
        self.record(
            session_key,
            turn_id,
            "llm_response",
            {
                "iteration": iteration,
                "content_preview": preview(response.content),
                "tool_call_count": len(response.tool_calls),
                "tool_names": [tool_call.name for tool_call in response.tool_calls],
            },
        )

    def tool_call(self, session_key: str, turn_id: str, tool_call: ToolCall) -> None:
        self.record(
            session_key,
            turn_id,
            "tool_call",
            {
                "tool_call_id": tool_call.id,
                "tool_name": tool_call.name,
                "arguments": tool_call.arguments,
            },
        )

    def subagent_start(
        self,
        session_key: str,
        turn_id: str,
        tool_call: ToolCall,
        subagent_task_id: str,
        user_content: str,
        inherited_active_skills: list[str],
    ) -> None:
        self.record(
            session_key,
            turn_id,
            "subagent_start",
            {
                "tool_call_id": tool_call.id,
                "subagent_task_id": subagent_task_id,
                "agent_type": tool_call.arguments.get("agent_type", "researcher"),
                "delegation_reason": tool_call.arguments.get("reason", ""),
                "delegation_mode": delegation_mode(tool_call.arguments, user_content),
                "inherited_active_skills": inherited_active_skills,
                "task_preview": preview(str(tool_call.arguments.get("task", ""))),
            },
        )

    def subagent_result(
        self,
        session_key: str,
        turn_id: str,
        tool_call: ToolCall,
        subagent_task_id: str,
        result: str,
    ) -> None:
        self.record(
            session_key,
            turn_id,
            "subagent_result",
            {
                "tool_call_id": tool_call.id,
                "subagent_task_id": subagent_task_id,
                "delegation_reason": tool_call.arguments.get("reason", ""),
                "result_preview": preview(result),
                "result_length": len(result),
            },
        )

    def tool_result(
        self,
        session_key: str,
        turn_id: str,
        tool_call: ToolCall,
        result: str,
    ) -> None:
        self.record(
            session_key,
            turn_id,
            "tool_result",
            {
                "tool_call_id": tool_call.id,
                "tool_name": tool_call.name,
                "result_preview": preview(result),
                "result_length": len(result),
            },
        )

    def memory_extraction_error(
        self,
        session_key: str,
        turn_id: str,
        phase: str,
        exc: Exception,
    ) -> None:
        self.record(
            session_key,
            turn_id,
            "memory_extraction_error",
            {"phase": phase, "type": type(exc).__name__, "message": str(exc)},
        )

    def memory_candidates_saved(
        self,
        session_key: str,
        turn_id: str,
        phase: str,
        memory_ids: list[str],
    ) -> None:
        if not memory_ids:
            return
        self.record(
            session_key,
            turn_id,
            "memory_candidates_saved",
            {"phase": phase, "memory_ids": memory_ids, "count": len(memory_ids)},
        )

    def conversation_summary_checked(
        self,
        session_key: str,
        turn_id: str,
        data: dict[str, Any],
    ) -> None:
        self.record(session_key, turn_id, "conversation_summary_checked", data)

    def conversation_summary_failed(
        self,
        session_key: str,
        turn_id: str,
        data: dict[str, Any],
        exc: Exception,
    ) -> None:
        self.record(
            session_key,
            turn_id,
            "conversation_summary_failed",
            {**data, "type": type(exc).__name__, "message": str(exc)},
        )

    def conversation_summary_updated(
        self,
        session_key: str,
        turn_id: str,
        data: dict[str, Any],
    ) -> None:
        self.record(session_key, turn_id, "conversation_summary_updated", data)

    def conversation_summary_data(
        self,
        history: list[Message],
        state: ConversationSummaryState | None,
        decision: Any,
        *,
        keep_recent_messages: int,
        reason: str,
        previous_state: ConversationSummaryState | None = None,
        budget_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        before = previous_state if previous_state is not None else state
        data: dict[str, Any] = {
            "history_messages": len(history),
            "summarized_message_count_before": (
                before.summarized_message_count if before else 0
            ),
            "summarized_message_count_after": (
                state.summarized_message_count if state else 0
            ),
            "new_messages_considered": decision.new_message_count,
            "kept_recent_messages": keep_recent_messages,
            "summary_chars_before": len(before.content) if before else 0,
            "summary_chars_after": len(state.content) if state else 0,
            "revision": state.revision if state else 0,
            "reason": reason,
        }
        if budget_data:
            data.update(budget_data)
        return data


def preview(text: str, limit: int = 300) -> str:
    """Return a compact single-line preview for trace files."""
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


def delegation_mode(arguments: dict[str, Any], user_content: str) -> str:
    """Infer whether delegation was explicitly requested or chosen by the agent."""
    marker_text = " ".join(
        [
            user_content.lower(),
            *[
                str(value).lower()
                for key, value in arguments.items()
                if key in {"task", "context", "reason"}
            ],
        ]
    )
    explicit_markers = (
        "subagent",
        "sub-agent",
        "delegate",
        "researcher",
        "reviewer",
        "委托",
        "子 agent",
    )
    if any(marker in marker_text for marker in explicit_markers):
        return "explicit"
    return "automatic"
