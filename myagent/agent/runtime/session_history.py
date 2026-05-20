"""Session history and summary compaction for AgentLoop."""

from __future__ import annotations

from myagent.agent.context.types import ContextBudget, Message
from myagent.agent.context.summary import (
    ConversationSummarizer,
    ConversationSummaryConfig,
    ConversationSummaryState,
)
from myagent.memory.extractor import MemoryExtractor


class AgentSessionHistory:
    """Own per-session raw history and its compact summary view."""

    def __init__(
        self,
        summarizer: ConversationSummarizer,
        config: ConversationSummaryConfig,
        memory_extractor: MemoryExtractor | None,
    ) -> None:
        self.summarizer = summarizer
        self.config = config
        self.memory_extractor = memory_extractor
        self.raw: dict[str, list[Message]] = {}
        self.summaries: dict[str, ConversationSummaryState] = {}
        self.current_summary_session_key: str | None = None

    def history_for(self, session_key: str) -> list[Message]:
        """Return mutable raw history for a session."""
        return self.raw.setdefault(session_key, [])

    def set_current_summary_session(self, session_key: str) -> None:
        self.current_summary_session_key = session_key

    def clear_current_summary_session(self) -> None:
        self.current_summary_session_key = None

    def visible_history_for_context(
        self,
        session_key: str,
        history: list[Message],
    ) -> list[Message]:
        """Return raw history not already covered by the session summary."""
        state = self.summaries.get(session_key)
        if state is None:
            return history
        start = min(max(state.summarized_message_count, 0), len(history))
        return history[start:]

    def current_summary_context(self) -> str:
        """Return the current session summary as model-visible background."""
        if not self.current_summary_session_key:
            return ""
        state = self.summaries.get(self.current_summary_session_key)
        if state is None or not state.content.strip():
            return ""
        return (
            "The following is a compact summary of earlier conversation context.\n"
            "Use it as background, not as current instructions. Recent user messages "
            "and system instructions override this summary.\n\n"
            f"{state.content.strip()}"
        )

    async def compact_before_context(
        self,
        session_key: str,
        turn_id: str,
        history: list[Message],
        budget: ContextBudget,
    ) -> bool:
        """Flush and summarize older history before building model context."""
        visible_history = self.visible_history_for_context(session_key, history)
        history_limit = budget.raw_history_token_limit
        if history_limit <= 0 or not visible_history:
            return False

        visible_tokens = self.summarizer.estimate_messages_tokens(visible_history)
        if visible_tokens <= history_limit:
            return False

        state = self.summaries.get(session_key)
        decision = self.summarizer.decide_for_budget(
            history,
            state,
            target_history_tokens=budget.raw_history_target_tokens,
        )
        if not decision.should_update:
            return False

        start = state.summarized_message_count if state else 0
        await self._flush_memory_before_summary(
            session_key,
            turn_id,
            history[start:decision.eligible_end],
        )
        try:
            updated = await self.summarizer.summarize(
                session_key,
                history,
                state,
                decision,
            )
        except Exception:
            return False

        self.summaries[session_key] = updated
        pruned_count = self._prune_summarized_history(history, updated.summarized_message_count)
        if pruned_count:
            updated = ConversationSummaryState(
                session_key=updated.session_key,
                content=updated.content,
                summarized_message_count=0,
                source_message_count=updated.source_message_count,
                revision=updated.revision,
                updated_at=updated.updated_at,
                estimated_tokens=updated.estimated_tokens,
            )
            self.summaries[session_key] = updated
        updated = await self._compress_summary_if_needed(
            session_key,
            turn_id,
            updated,
            budget,
        )
        self.summaries[session_key] = updated
        return True

    async def _flush_memory_before_summary(
        self,
        session_key: str,
        turn_id: str,
        messages: list[Message],
    ) -> None:
        if not messages or self.memory_extractor is None:
            return
        try:
            await self.memory_extractor.extract_messages(
                messages,
                source="pre_context_compaction",
            )
        except Exception:
            return

    def _prune_summarized_history(self, history: list[Message], count: int) -> int:
        pruned_count = min(max(count, 0), len(history))
        if pruned_count:
            del history[:pruned_count]
        return pruned_count

    async def _compress_summary_if_needed(
        self,
        session_key: str,
        turn_id: str,
        state: ConversationSummaryState,
        budget: ContextBudget,
    ) -> ConversationSummaryState:
        if state.estimated_tokens <= budget.summary_token_limit:
            return state
        try:
            compressed = await self.summarizer.compress_summary(
                state,
                token_limit=budget.summary_token_limit,
                max_rounds=budget.max_compression_rounds,
            )
        except Exception:
            return state
        return compressed
