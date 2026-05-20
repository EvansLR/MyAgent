"""Single-turn orchestration for the main agent loop."""

from __future__ import annotations

from uuid import uuid4

from myagent.agent.context import ContextBuilder
from myagent.agent.runtime.run_events import AgentRunEvents
from myagent.agent.runtime.session_history import AgentSessionHistory
from myagent.agent.runtime.skill_state import AgentSkillState
from myagent.agent.runtime.tool_loop import AgentToolLoop, AgentTurnState
from myagent.bus import InboundMessage, MessageBus, OutboundMessage
from myagent.memory import VisibleMemoryCompressor
from myagent.profile import ProfileLoader
from myagent.tools import ToolRegistry


class AgentTurnProcessor:
    """Prepare context, run model/tool work, and persist one completed turn."""

    def __init__(
        self,
        *,
        bus: MessageBus,
        context_builder: ContextBuilder,
        session_history: AgentSessionHistory,
        memory_compressor: VisibleMemoryCompressor,
        events: AgentRunEvents,
        skill_state: AgentSkillState,
        tool_registry: ToolRegistry,
        tool_loop: AgentToolLoop,
        profile_loader: ProfileLoader,
        max_tool_iterations: int,
    ) -> None:
        self.bus = bus
        self.context_builder = context_builder
        self.session_history = session_history
        self.memory_compressor = memory_compressor
        self.events = events
        self.skill_state = skill_state
        self.tool_registry = tool_registry
        self.tool_loop = tool_loop
        self.profile_loader = profile_loader
        self.max_tool_iterations = max_tool_iterations

    async def process_message(self, inbound: InboundMessage) -> OutboundMessage:
        """Generate and publish an outbound response for one inbound message."""
        turn_id = uuid4().hex
        turn_state = AgentTurnState(
            session_key=inbound.session_key,
            turn_id=turn_id,
            max_iterations=self.max_tool_iterations,
        )
        self._start_message_tool_turn(inbound)
        self.events.user_message(inbound, turn_id)
        self.events.profile_loaded(
            inbound.session_key,
            turn_id,
            self.profile_loader.to_trace_data(),
        )
        history = self.session_history.history_for(inbound.session_key)
        self.session_history.set_current_summary_session(inbound.session_key)
        await self._compress_visible_memory_before_context(inbound.session_key, turn_id)
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
        self.skill_state.start_turn(inbound.session_key, turn_id)
        try:
            content = await self.tool_loop.generate(messages, inbound, turn_state)
        except Exception as exc:
            turn_state.stop_reason = "provider_error"
            content = f"Error: {exc}"
            self.events.error(inbound.session_key, turn_id, exc)

        outbound = await self._publish_final_reply_if_needed(inbound, turn_id, content, turn_state)
        history.extend(
            [
                {"role": "user", "content": inbound.content},
                {"role": "assistant", "content": content},
            ]
        )
        self.skill_state.end_turn(inbound.session_key, turn_id)
        self.session_history.clear_current_summary_session()
        return outbound

    def _start_message_tool_turn(self, inbound: InboundMessage) -> None:
        message_tool = self.tool_registry.get("message")
        if message_tool is None or not hasattr(message_tool, "set_context"):
            return
        message_tool.set_context(inbound.channel, inbound.chat_id)
        message_tool.start_turn()

    async def _publish_final_reply_if_needed(
        self,
        inbound: InboundMessage,
        turn_id: str,
        content: str,
        turn_state: AgentTurnState,
    ) -> OutboundMessage:
        message_sent = False
        message_tool = self.tool_registry.get("message")
        if message_tool is not None and hasattr(message_tool, "_sent_in_turn"):
            message_sent = message_tool._sent_in_turn

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
            return outbound

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
        return outbound

    async def _compress_visible_memory_before_context(
        self,
        session_key: str,
        turn_id: str,
    ) -> None:
        """Keep visible memory within its prompt-time token limit."""
        budget = self.context_builder.budget
        try:
            result = await self.memory_compressor.compress_if_needed(
                token_limit=budget.memory_token_limit,
                max_rounds=budget.max_compression_rounds,
            )
        except Exception as exc:
            self.events.record(
                session_key,
                turn_id,
                "memory_compression_failed",
                {"type": type(exc).__name__, "message": str(exc)},
            )
            return
        if not result.changed:
            return
        self.events.record(
            session_key,
            turn_id,
            "memory_compressed",
            {
                "estimated_tokens": result.estimated_tokens,
                "rounds": result.rounds,
                "truncated": result.truncated,
            },
        )
