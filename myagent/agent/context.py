"""Context assembly for model calls."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import os
from pathlib import Path
import platform
from typing import Any, Callable

from myagent.bus import InboundMessage
from myagent.skills import SkillRegistry

Message = dict[str, Any]
DEFAULT_DELEGATION_POLICY = (
    "Use delegate_task proactively when a user request benefits from isolated "
    "research, codebase exploration, review, or large intermediate analysis. "
    "Do not require the user to explicitly ask for a subagent. Keep final "
    "control in the main assistant: use the subagent result as evidence, then "
    "synthesize the final answer yourself. Prefer researcher for factual "
    "research and local/web evidence gathering, reviewer for checking risks or "
    "gaps, and interviewer for interview-style explanations. Do not delegate "
    "simple direct answers or tasks where the main assistant can answer clearly "
    "without extra exploration."
)


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
        runtime_environment: str | None = None,
        delegation_policy: str | None = DEFAULT_DELEGATION_POLICY,
        core_memory_provider: Callable[[], str] | None = None,
        active_skills_provider: Callable[[], str] | None = None,
        skill_registry: SkillRegistry | None = None,
        budget: ContextBudget | None = None,
    ) -> None:
        self.identity = identity or (
            "You are MyAgent, a lightweight ReAct agent runtime for learning "
            "and interview practice. Be concise, helpful, and honest about "
            "current limitations."
        )
        self.runtime_environment = runtime_environment
        self.delegation_policy = delegation_policy
        self.core_memory_provider = core_memory_provider
        self.active_skills_provider = active_skills_provider
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
        if self.runtime_environment:
            sections.append(
                ContextSection(
                    name="Runtime Environment",
                    content=self.runtime_environment,
                    priority=5,
                    tier=ContextTier.PROTECTED,
                    source="runtime:environment",
                )
            )
        core_memory = self.read_core_memory()
        if self.delegation_policy:
            sections.append(
                ContextSection(
                    name="Delegation Policy",
                    content=self.delegation_policy,
                    priority=8,
                    tier=ContextTier.PROTECTED,
                    source="agent:delegation_policy",
                )
            )
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
        active_skills = self.read_active_skills()
        if active_skills:
            sections.append(
                ContextSection(
                    name="Active Skills",
                    content=active_skills,
                    priority=20,
                    tier=ContextTier.MEDIUM,
                    source="skills:active",
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

    def read_active_skills(self) -> str:
        """Read compact current-turn active skill context for the system prompt."""
        if self.active_skills_provider is None:
            return ""
        return self.active_skills_provider().strip()

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


def format_runtime_environment(
    workspace_root: Path | str | None = None,
    now: datetime | None = None,
) -> str:
    """Return stable runtime facts that help the model call local tools correctly."""
    root = Path(workspace_root or ".").resolve()
    current = now or datetime.now().astimezone()
    os_name = platform.system() or "Unknown"
    shell = _detect_shell(os_name)
    path_style = "Windows paths" if os_name == "Windows" else "POSIX paths"
    timezone = current.tzname() or "local timezone"
    return "\n".join(
        [
            f"- Current date: {current.date().isoformat()}",
            f"- Current time: {current.strftime('%H:%M:%S')} {timezone}",
            f"- OS: {os_name}",
            f"- Shell: {shell}",
            f"- Workspace root: {root}",
            f"- Path style: {path_style}",
            "- Resolve relative dates such as today, tomorrow, and yesterday to absolute dates before searching.",
            "- Filesystem tools resolve relative paths inside the workspace root.",
            "- Common personal folder aliases such as Desktop, Downloads, Documents, and 桌面 are recognized.",
            "- Read-only filesystem operations do not require approval.",
            "- Mutating filesystem operations outside the workspace require explicit user approval from the current channel.",
            "- Prefer relative paths such as '.' unless the user asks for a specific external location.",
            "- Do not invent absolute paths.",
        ]
    )


def _detect_shell(os_name: str) -> str:
    if os_name == "Windows":
        parent = (os.environ.get("PSModulePath") or "").lower()
        if "powershell" in parent:
            return "PowerShell"
        return "Windows shell"
    return os.environ.get("SHELL") or "Unknown shell"
