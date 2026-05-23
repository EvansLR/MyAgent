"""Shared data structures for context assembly."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from myagent.budget import (
    DEFAULT_CHARS_PER_TOKEN,
    DEFAULT_MAX_COMPRESSION_ROUNDS,
    DEFAULT_MAX_PROMPT_TOKENS,
    DEFAULT_MEMORY_TOKEN_LIMIT,
    DEFAULT_RAW_HISTORY_TARGET_TOKENS,
    DEFAULT_RAW_HISTORY_TOKEN_LIMIT,
    DEFAULT_SUMMARY_TOKEN_LIMIT,
)

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
    """Budget knobs for context, memory, and history compaction."""

    max_prompt_tokens: int | None = DEFAULT_MAX_PROMPT_TOKENS
    chars_per_token: int = DEFAULT_CHARS_PER_TOKEN
    memory_token_limit: int = DEFAULT_MEMORY_TOKEN_LIMIT
    summary_token_limit: int = DEFAULT_SUMMARY_TOKEN_LIMIT
    raw_history_token_limit: int = DEFAULT_RAW_HISTORY_TOKEN_LIMIT
    raw_history_target_tokens: int = DEFAULT_RAW_HISTORY_TARGET_TOKENS
    max_compression_rounds: int = DEFAULT_MAX_COMPRESSION_ROUNDS
