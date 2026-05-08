"""Context assembly for model calls."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable

from myagent.bus import InboundMessage
from myagent.skills import SkillRegistry

Message = dict[str, Any]


class ContextTier(StrEnum):
    """Priority class used by the context composer."""

    PROTECTED = "protected"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    EPHEMERAL = "ephemeral"


@dataclass(frozen=True, slots=True)
class ContextSection:
    """One section of the system prompt."""

    name: str
    content: str
    priority: int = 100
    tier: ContextTier = ContextTier.MEDIUM
    source: str = "runtime"


@dataclass(frozen=True, slots=True)
class ContextBudget:
    """Budget knobs for first-stage context selection."""

    max_prompt_tokens: int | None = None
    max_history_messages: int = 20
    chars_per_token: int = 4


@dataclass(frozen=True, slots=True)
class ContextSectionReport:
    """Observable size and inclusion data for one section."""

    name: str
    tier: str
    priority: int
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


@dataclass(frozen=True, slots=True)
class ContextAssemblyReport:
    """Report describing what ContextBuilder assembled for one model call."""

    total_chars: int
    estimated_tokens: int
    message_count: int
    sections: list[ContextSectionReport]
    history: ContextHistoryReport
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return a trace-friendly dictionary."""
        return {
            "total_chars": self.total_chars,
            "estimated_tokens": self.estimated_tokens,
            "message_count": self.message_count,
            "sections": [
                {
                    "name": section.name,
                    "tier": section.tier,
                    "priority": section.priority,
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
            },
            "warnings": list(self.warnings),
        }


class ContextBuilder:
    """Build model messages from identity, placeholders, and conversation."""

    def __init__(
        self,
        identity: str | None = None,
        core_memory_provider: Callable[[], str] | None = None,
        skill_registry: SkillRegistry | None = None,
        budget: ContextBudget | None = None,
    ) -> None:
        self.identity = identity or (
            "You are MyAgent, a lightweight ReAct agent runtime for learning "
            "and interview practice. Be concise, helpful, and honest about "
            "current limitations."
        )
        self.core_memory_provider = core_memory_provider
        self.skill_registry = skill_registry
        self.budget = budget or ContextBudget()
        self.last_report: ContextAssemblyReport | None = None

    def build_sections(self) -> list[ContextSection]:
        """Return system prompt sections in first-stage priority order."""
        sections = [
            ContextSection(
                name="Identity",
                content=self.identity,
                priority=1,
                tier=ContextTier.PROTECTED,
                source="identity",
            ),
        ]
        core_memory = self.read_core_memory()
        if core_memory:
            sections.append(
                ContextSection(
                    name="Core Memory",
                    content=core_memory,
                    priority=10,
                    tier=ContextTier.HIGH,
                    source="memory:core",
                )
            )
        skills_content = self.format_skills()
        if skills_content:
            sections.append(
                ContextSection(
                    name="Available Skills",
                    content=skills_content,
                    priority=30,
                    tier=ContextTier.MEDIUM,
                    source="skills:summary",
                )
            )
        return sections

    def build_system_prompt(self) -> str:
        """Build the system prompt from ordered sections."""
        sections = sorted(self.build_sections(), key=lambda section: section.priority)
        return "\n\n---\n\n".join(
            f"# {section.name}\n\n{section.content.strip()}"
            for section in sections
            if section.content.strip()
        )

    def build_messages(
        self,
        current_message: InboundMessage,
        history: list[Message] | None = None,
    ) -> list[Message]:
        """Build the messages sent to a provider."""
        messages, report = self.build_messages_with_report(current_message, history)
        self.last_report = report
        return messages

    def build_messages_with_report(
        self,
        current_message: InboundMessage,
        history: list[Message] | None = None,
    ) -> tuple[list[Message], ContextAssemblyReport]:
        """Build model messages and return a context assembly report."""
        selected_history, history_report, warnings = self.select_history(history or [])
        return [
            {"role": "system", "content": self.build_system_prompt()},
            *selected_history,
            {"role": "user", "content": current_message.content},
        ], self._build_report(
            current_message=current_message,
            selected_history=selected_history,
            history_report=history_report,
            warnings=warnings,
        )

    def select_history(
        self,
        history: list[Message],
    ) -> tuple[list[Message], ContextHistoryReport, list[str]]:
        """Select the history slice visible to the current model call."""
        max_messages = max(self.budget.max_history_messages, 0)
        dropped = max(len(history) - max_messages, 0)
        selected = history[-max_messages:] if max_messages else []
        warnings = ["history_trimmed"] if dropped else []
        return (
            selected,
            ContextHistoryReport(
                total_messages=len(history),
                included_messages=len(selected),
                dropped_messages=dropped,
                max_history_messages=max_messages,
            ),
            warnings,
        )

    def read_core_memory(self) -> str:
        """Read always-visible long-term memory for the system prompt."""
        if self.core_memory_provider is None:
            return ""
        return self.core_memory_provider().strip()

    def format_skills(self) -> str:
        """Format available skills for the system prompt."""
        if self.skill_registry is None:
            return ""
        return self.skill_registry.format_for_context()

    def _build_report(
        self,
        current_message: InboundMessage,
        selected_history: list[Message],
        history_report: ContextHistoryReport,
        warnings: list[str],
    ) -> ContextAssemblyReport:
        system_prompt = self.build_system_prompt()
        sections = [
            ContextSectionReport(
                name=section.name,
                tier=section.tier.value,
                priority=section.priority,
                source=section.source,
                chars=len(section.content.strip()),
                estimated_tokens=_estimate_tokens(section.content, self.budget.chars_per_token),
                included=bool(section.content.strip()),
                reason="included" if section.content.strip() else "empty",
            )
            for section in sorted(self.build_sections(), key=lambda item: item.priority)
        ]
        messages: list[Message] = [
            {"role": "system", "content": system_prompt},
            *selected_history,
            {"role": "user", "content": current_message.content},
        ]
        total_chars = sum(len(str(message.get("content", ""))) for message in messages)
        return ContextAssemblyReport(
            total_chars=total_chars,
            estimated_tokens=_estimate_tokens(system_prompt, self.budget.chars_per_token)
            + sum(
                _estimate_tokens(str(message.get("content", "")), self.budget.chars_per_token)
                for message in selected_history
            )
            + _estimate_tokens(current_message.content, self.budget.chars_per_token),
            message_count=len(messages),
            sections=sections,
            history=history_report,
            warnings=warnings,
        )


def _estimate_tokens(text: str, chars_per_token: int) -> int:
    divisor = max(chars_per_token, 1)
    return max((len(text) + divisor - 1) // divisor, 0)
