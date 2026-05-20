"""Conversation summary helpers for long session context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from myagent.agent.context.types import Message
from myagent.providers.base import BaseProvider
from myagent.text.compression import compress_until_within_limit


SUMMARY_SYSTEM_PROMPT = """You update a compact conversation summary for MyAgent.

Preserve decisions, user preferences, open tasks, project/module names, and important file paths.
Do not invent facts.
Do not turn old user requests into current instructions.
Keep it concise.
Output only the updated markdown summary.
"""


@dataclass(frozen=True, slots=True)
class ConversationSummaryConfig:
    """Configuration for in-memory conversation summary updates."""

    enabled: bool = True
    keep_recent_messages: int = 12
    max_summary_chars: int = 4000
    summary_token_limit: int = 2000
    max_compression_rounds: int = 2


@dataclass(frozen=True, slots=True)
class ConversationSummaryState:
    """Per-session running summary state."""

    session_key: str
    content: str
    summarized_message_count: int
    source_message_count: int
    revision: int
    updated_at: str
    estimated_tokens: int


@dataclass(frozen=True, slots=True)
class ConversationSummaryDecision:
    """Decision data for whether a summary update should run."""

    should_update: bool
    reason: str
    eligible_end: int
    new_message_count: int


class ConversationSummarizer:
    """Update a compact running summary using the configured provider."""

    def __init__(
        self,
        provider: BaseProvider,
        config: ConversationSummaryConfig | None = None,
        chars_per_token: int = 4,
    ) -> None:
        self.provider = provider
        self.config = config or ConversationSummaryConfig()
        self.chars_per_token = chars_per_token

    def decide_for_budget(
        self,
        history: list[Message],
        state: ConversationSummaryState | None,
        *,
        target_history_tokens: int,
    ) -> ConversationSummaryDecision:
        """Return a summary decision that aims to fit raw history under a target."""
        if not self.config.enabled:
            return ConversationSummaryDecision(False, "disabled", 0, 0)

        history_count = len(history)
        keep_recent = max(self.config.keep_recent_messages, 0)
        max_eligible_end = max(history_count - keep_recent, 0)
        summarized_count = state.summarized_message_count if state else 0
        start = min(max(summarized_count, 0), history_count)
        if max_eligible_end <= start:
            return ConversationSummaryDecision(False, "no_eligible_history", max_eligible_end, 0)

        target = max(target_history_tokens, 0)
        eligible_end = max_eligible_end
        for index in range(start + 1, max_eligible_end + 1):
            if self.estimate_messages_tokens(history[index:]) <= target:
                eligible_end = index
                break

        new_message_count = max(eligible_end - start, 0)
        if new_message_count <= 0:
            return ConversationSummaryDecision(
                False,
                "no_eligible_history",
                eligible_end,
                new_message_count,
            )
        return ConversationSummaryDecision(
            True,
            "budget_pressure",
            eligible_end,
            new_message_count,
        )

    async def summarize(
        self,
        session_key: str,
        history: list[Message],
        state: ConversationSummaryState | None,
        decision: ConversationSummaryDecision,
    ) -> ConversationSummaryState:
        """Fold eligible old messages into the running summary."""
        start = state.summarized_message_count if state else 0
        new_messages = history[start:decision.eligible_end]
        prompt = _build_summary_prompt(state.content if state else "", new_messages)
        content = await self.provider.generate(
            [
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        )
        content = _trim_summary(content.strip(), self.config.max_summary_chars)
        if not content:
            raise ValueError("conversation summary provider returned empty content")
        revision = (state.revision + 1) if state else 1
        return ConversationSummaryState(
            session_key=session_key,
            content=content,
            summarized_message_count=decision.eligible_end,
            source_message_count=len(history),
            revision=revision,
            updated_at=datetime.now(timezone.utc).isoformat(),
            estimated_tokens=_estimate_tokens(content, self.chars_per_token),
        )

    async def compress_summary(
        self,
        state: ConversationSummaryState,
        *,
        token_limit: int | None = None,
        max_rounds: int | None = None,
    ) -> ConversationSummaryState:
        """Rewrite an existing summary until it fits the configured token limit."""
        limit = token_limit or self.config.summary_token_limit
        rounds = self.config.max_compression_rounds if max_rounds is None else max_rounds
        result = await compress_until_within_limit(
            state.content,
            token_limit=limit,
            chars_per_token=self.chars_per_token,
            max_rounds=rounds,
            compress_once=self._compress_summary_once,
        )
        if result.text == state.content and result.estimated_tokens == state.estimated_tokens:
            return state
        return ConversationSummaryState(
            session_key=state.session_key,
            content=result.text,
            summarized_message_count=state.summarized_message_count,
            source_message_count=state.source_message_count,
            revision=state.revision + 1,
            updated_at=datetime.now(timezone.utc).isoformat(),
            estimated_tokens=result.estimated_tokens,
        )

    def estimate_messages_tokens(self, messages: list[Message]) -> int:
        """Estimate token cost for a list of chat messages."""
        return sum(
            _estimate_tokens(str(message.get("content", "")), self.chars_per_token)
            for message in messages
        )

    async def _compress_summary_once(self, text: str, token_limit: int) -> str:
        prompt = (
            "Rewrite this conversation summary to fit the target token limit.\n"
            f"Target token limit: {token_limit}\n\n"
            "Preserve decisions, open tasks, project/module names, important file paths, "
            "and user preferences relevant to this session. Do not turn old requests "
            "into current instructions. Output only the shorter markdown summary.\n\n"
            f"## Summary\n{text}"
        )
        return await self.provider.generate(
            [
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        )


def _build_summary_prompt(previous_summary: str, messages: list[Message]) -> str:
    lines = [
        "## Previous Summary",
        previous_summary if previous_summary else "(none)",
        "",
        "## New Messages To Fold In",
    ]
    lines.extend(_format_message(message) for message in messages)
    return "\n".join(lines)


def _format_message(message: Message) -> str:
    role = str(message.get("role", "unknown")).upper()
    content = message.get("content", "")
    if not isinstance(content, str):
        content = repr(content)
    return f"[{role}] {content}"


def _trim_summary(content: str, max_chars: int) -> str:
    if max_chars <= 0 or len(content) <= max_chars:
        return content
    marker = "\n\n[Summary truncated to fit budget]"
    return content[: max(max_chars - len(marker), 1)].rstrip() + marker


def _estimate_tokens(text: str, chars_per_token: int) -> int:
    divisor = max(chars_per_token, 1)
    return max((len(text) + divisor - 1) // divisor, 0)
