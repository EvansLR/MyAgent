"""Single-turn orchestration for the main agent loop."""

from __future__ import annotations

from uuid import uuid4

from myagent.agent.context import ContextBuilder
from myagent.agent.runtime.session_history import AgentSessionHistory
from myagent.agent.runtime.skill_state import AgentSkillState
from myagent.agent.runtime.tool_loop import AgentToolLoop, AgentTurnState
from myagent.bus import InboundMessage, MessageBus, OutboundMessage
from myagent.memory import VisibleMemoryCompressor


class AgentTurnProcessor:
    """Prepare context, run model/tool work, and persist one completed turn."""

    def __init__(
        self,
        *,
        bus: MessageBus,
        context_builder: ContextBuilder,
        session_history: AgentSessionHistory,
        memory_compressor: VisibleMemoryCompressor,
        skill_state: AgentSkillState,
        tool_loop: AgentToolLoop,
        max_tool_iterations: int,
    ) -> None:
        self.bus = bus
        self.context_builder = context_builder
        self.session_history = session_history
        self.memory_compressor = memory_compressor
        self.skill_state = skill_state
        self.tool_loop = tool_loop
        self.max_tool_iterations = max_tool_iterations

    async def process_message(self, inbound: InboundMessage) -> OutboundMessage:
        """Generate and publish an outbound response for one inbound message."""
        turn_id = uuid4().hex
        turn_state = AgentTurnState(
            session_key=inbound.session_key,
            turn_id=turn_id,
            max_iterations=self.max_tool_iterations,
        )
        history = self.session_history.history_for(inbound.session_key)
        self.session_history.set_current_summary_session(inbound.session_key)
        await self._compress_visible_memory_before_context()
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
        messages = self.context_builder.build_messages(
            inbound,
            visible_history,
        )
        self.skill_state.start_turn(inbound.session_key, turn_id)
        try:
            content = await self.tool_loop.generate(messages, inbound, turn_state)
        except Exception as exc:
            turn_state.stop_reason = "provider_error"
            content = f"Error: {exc}"

        outbound = await self._publish_final_reply(inbound, content, turn_state)
        history.extend(
            [
                {"role": "user", "content": inbound.content},
                {"role": "assistant", "content": content},
            ]
        )
        self.skill_state.end_turn(inbound.session_key, turn_id)
        self.session_history.clear_current_summary_session()
        return outbound

    async def _publish_final_reply(
        self,
        inbound: InboundMessage,
        content: str,
        turn_state: AgentTurnState,
    ) -> OutboundMessage:
        if not turn_state.stop_reason:
            turn_state.stop_reason = "final_output"
        outbound = OutboundMessage(
            channel=inbound.channel,
            chat_id=inbound.chat_id,
            content=content,
            media=list(turn_state.attachments),
        )
        await self.bus.publish_outbound(outbound)
        return outbound

    async def _compress_visible_memory_before_context(self) -> None:
        """Keep visible memory within its prompt-time token limit."""
        try:
            await self.memory_compressor.compress_if_needed()
        except Exception:
            return
