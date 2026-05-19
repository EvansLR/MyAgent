"""Conversation summary helpers for long session context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from myagent.agent.context import Message
from myagent.providers.base import BaseProvider


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
    trigger_messages: int = 24
    trigger_tokens: int | None = 3000
    keep_recent_messages: int = 12
    min_new_messages: int = 6
    max_summary_chars: int = 4000


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

    def decide(
        self,
        history: list[Message],
        state: ConversationSummaryState | None = None,
        *,
        force: bool = False,
    ) -> ConversationSummaryDecision:
        """Return whether enough old history exists to update the summary."""
        if not self.config.enabled:
            return ConversationSummaryDecision(False, "disabled", 0, 0)
        history_count = len(history)
        history_tokens = sum(
            _estimate_tokens(str(message.get("content", "")), self.chars_per_token)
            for message in history
        )
        token_pressure = (
            self.config.trigger_tokens is not None
            and history_tokens >= self.config.trigger_tokens
        )
        if not force and history_count < self.config.trigger_messages and not token_pressure:
            return ConversationSummaryDecision(False, "below_trigger", 0, 0)
        keep_recent = max(self.config.keep_recent_messages, 0)
        eligible_end = max(history_count - keep_recent, 0)
        summarized_count = state.summarized_message_count if state else 0
        new_message_count = max(eligible_end - summarized_count, 0)
        if new_message_count <= 0:
            return ConversationSummaryDecision(
                False,
                "no_eligible_history",
                eligible_end,
                new_message_count,
            )
        if new_message_count < self.config.min_new_messages and not token_pressure and not force:
            return ConversationSummaryDecision(
                False,
                "not_enough_new_messages",
                eligible_end,
                new_message_count,
            )
        return ConversationSummaryDecision(
            True,
            "forced" if force else "ready",
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
