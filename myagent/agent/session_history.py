"""Session history and summary compaction for AgentLoop."""

from __future__ import annotations

from myagent.agent.context_types import ContextBudget, Message
from myagent.agent.run_events import AgentRunEvents
from myagent.agent.summary import (
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
        events: AgentRunEvents,
    ) -> None:
        self.summarizer = summarizer
        self.config = config
        self.memory_extractor = memory_extractor
        self.events = events
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
        history_budget = self._history_compaction_budget(visible_history, budget)
        if history_budget is None:
            return False

        visible_tokens = self.summarizer.estimate_messages_tokens(visible_history)
        if visible_tokens <= history_budget:
            return False

        state = self.summaries.get(session_key)
        target_tokens = int(
            history_budget
            * min(max(self.config.compact_target_ratio, 0.0), 1.0)
        )
        decision = self.summarizer.decide_for_budget(
            history,
            state,
            target_history_tokens=target_tokens,
        )
        budget_data = {
            "history_budget_tokens": history_budget,
            "target_history_tokens": target_tokens,
            "visible_history_tokens": visible_tokens,
        }
        if not decision.should_update:
            self.events.conversation_summary_checked(
                session_key,
                turn_id,
                self.events.conversation_summary_data(
                    history,
                    state,
                    decision,
                    keep_recent_messages=self.config.keep_recent_messages,
                    reason=f"pre_context_{decision.reason}",
                    budget_data=budget_data,
                ),
            )
            return False

        start = state.summarized_message_count if state else 0
        await self._flush_memory_before_summary(
            session_key,
            turn_id,
            history[start:decision.eligible_end],
        )
        self.events.conversation_summary_checked(
            session_key,
            turn_id,
            self.events.conversation_summary_data(
                history,
                state,
                decision,
                keep_recent_messages=self.config.keep_recent_messages,
                reason="pre_context_budget_pressure",
                budget_data=budget_data,
            ),
        )
        try:
            updated = await self.summarizer.summarize(
                session_key,
                history,
                state,
                decision,
            )
        except Exception as exc:
            self.events.conversation_summary_failed(
                session_key,
                turn_id,
                self.events.conversation_summary_data(
                    history,
                    state,
                    decision,
                    keep_recent_messages=self.config.keep_recent_messages,
                    reason="pre_context_failed",
                    budget_data=budget_data,
                ),
                exc,
            )
            return False

        self.summaries[session_key] = updated
        self.events.conversation_summary_updated(
            session_key,
            turn_id,
            self.events.conversation_summary_data(
                history,
                updated,
                decision,
                keep_recent_messages=self.config.keep_recent_messages,
                previous_state=state,
                reason="pre_context_updated",
                budget_data={
                    **budget_data,
                    "raw_history_tokens_after": self.summarizer.estimate_messages_tokens(
                        self.visible_history_for_context(session_key, history)
                    ),
                },
            ),
        )
        return True

    def _history_compaction_budget(
        self,
        history: list[Message],
        budget: ContextBudget,
    ) -> int | None:
        if budget.max_prompt_tokens is None or not history:
            return None
        ratio = min(max(budget.history_token_ratio, 0.0), 1.0)
        return int(budget.max_prompt_tokens * ratio)

    async def _flush_memory_before_summary(
        self,
        session_key: str,
        turn_id: str,
        messages: list[Message],
    ) -> None:
        if not messages or self.memory_extractor is None:
            return
        try:
            memory_ids = await self.memory_extractor.extract_messages(
                messages,
                source="pre_context_compaction",
            )
        except Exception as exc:
            self.events.memory_extraction_error(
                session_key,
                turn_id,
                "pre_context",
                exc,
            )
            return
        self.events.memory_candidates_saved(
            session_key,
            turn_id,
            "pre_context",
            memory_ids,
        )
