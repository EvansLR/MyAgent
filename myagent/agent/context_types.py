"""Shared data structures for context assembly."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

Message = dict[str, Any]


class ContextRetention(StrEnum):
    """How strongly a system context section should survive final budgeting."""

    REQUIRED = "required"
    CORE = "core"
    CONTEXT = "context"
    OPTIONAL = "optional"


class ContextItemKind(StrEnum):
    """Source category for a piece of model-visible context."""

    INSTRUCTION = "instruction"
    MEMORY_CORE = "memory_core"
    SKILL_SUMMARY = "skill_summary"
    ACTIVE_SKILL = "active_skill"
    SESSION_SUMMARY = "session_summary"
    SESSION_HISTORY = "session_history"
    CURRENT_INPUT = "current_input"
    PROFILE = "profile"


@dataclass(frozen=True, slots=True)
class ContextSection:
    """One section of the system prompt."""

    name: str
    content: str
    source: str = "runtime"
    kind: ContextItemKind = ContextItemKind.INSTRUCTION
    retention: ContextRetention = ContextRetention.CONTEXT


@dataclass(frozen=True, slots=True)
class ContextBudget:
    """Budget knobs for first-stage context selection."""

    max_prompt_tokens: int | None = 6000
    max_history_messages: int | None = None
    chars_per_token: int = 4
    memory_token_limit: int = 6000
    summary_token_limit: int = 2000
    raw_history_token_limit: int = 12000
    raw_history_target_tokens: int = 6000
    max_compression_rounds: int = 2


@dataclass(frozen=True, slots=True)
class ContextItem:
    """Internal budgetable context unit."""

    id: str
    name: str
    kind: ContextItemKind
    retention: ContextRetention
    order: int
    source: str
    content: str
    estimated_tokens: int


@dataclass(frozen=True, slots=True)
class ContextSectionReport:
    """Observable size and inclusion data for one section."""

    name: str
    kind: str
    retention: str
    source: str
    chars: int
    estimated_tokens: int
    included: bool
    reason: str


@dataclass(frozen=True, slots=True)
class ContextHistoryReport:
    """Observable history selection data."""

    total_messages: int
    included_messages: int
    dropped_messages: int
    max_history_messages: int
    reserved_tokens: int = 0
    estimated_tokens: int = 0
    dropped_by_message_limit: int = 0
    dropped_by_token_budget: int = 0


@dataclass(frozen=True, slots=True)
class ContextAssemblyReport:
    """Report describing what ContextBuilder assembled for one model call."""

    total_chars: int
    estimated_tokens: int
    estimated_tokens_before_budget: int
    max_prompt_tokens: int | None
    message_count: int
    sections: list[ContextSectionReport]
    history: ContextHistoryReport
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return a trace-friendly dictionary."""
        return {
            "total_chars": self.total_chars,
            "estimated_tokens": self.estimated_tokens,
            "estimated_tokens_before_budget": self.estimated_tokens_before_budget,
            "max_prompt_tokens": self.max_prompt_tokens,
            "message_count": self.message_count,
            "sections": [
                {
                    "name": section.name,
                    "kind": section.kind,
                    "retention": section.retention,
                    "source": section.source,
                    "chars": section.chars,
                    "estimated_tokens": section.estimated_tokens,
                    "included": section.included,
                    "reason": section.reason,
                }
                for section in self.sections
            ],
            "history": {
                "total_messages": self.history.total_messages,
                "included_messages": self.history.included_messages,
                "dropped_messages": self.history.dropped_messages,
                "max_history_messages": self.history.max_history_messages,
                "reserved_tokens": self.history.reserved_tokens,
                "estimated_tokens": self.history.estimated_tokens,
                "dropped_by_message_limit": self.history.dropped_by_message_limit,
                "dropped_by_token_budget": self.history.dropped_by_token_budget,
            },
            "warnings": list(self.warnings),
        }

    @property
    def dropped_sections(self) -> list[ContextSectionReport]:
        """Return sections that were omitted after budgeting."""
        return [section for section in self.sections if not section.included]
