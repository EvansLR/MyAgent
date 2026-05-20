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

