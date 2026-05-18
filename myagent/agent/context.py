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


class ContextItemKind(StrEnum):
    """Source category for a piece of model-visible context."""

    INSTRUCTION = "instruction"
    MEMORY_CORE = "memory_core"
    SKILL_SUMMARY = "skill_summary"
    ACTIVE_SKILL = "active_skill"
    SESSION_SUMMARY = "session_summary"
    SESSION_HISTORY = "session_history"
    CURRENT_INPUT = "current_input"
    WORKSPACE = "workspace"


class ContextRetentionPolicy(StrEnum):
    """How a context item should behave when the prompt is over budget."""

    NEVER_DROP = "never_drop"
    KEEP_IF_FITS = "keep_if_fits"
    DROP_IF_NEEDED = "drop_if_needed"
    KEEP_RECENT_BY_TOKEN = "keep_recent_by_token"


@dataclass(frozen=True, slots=True)
class ContextSection:
    """One section of the system prompt."""

    name: str
    content: str
    priority: int = 100
    tier: ContextTier = ContextTier.MEDIUM
    source: str = "runtime"
    kind: ContextItemKind = ContextItemKind.INSTRUCTION
    policy: ContextRetentionPolicy = ContextRetentionPolicy.KEEP_IF_FITS


@dataclass(frozen=True, slots=True)
class ContextBudget:
    """Budget knobs for first-stage context selection."""

    max_prompt_tokens: int | None = 6000
    max_history_messages: int = 20
    chars_per_token: int = 4
    history_token_ratio: float = 0.35


@dataclass(frozen=True, slots=True)
class ContextItem:
    """Internal budgetable context unit."""

    id: str
    name: str
    kind: ContextItemKind
    tier: ContextTier
    priority: int
    source: str
    content: str
    policy: ContextRetentionPolicy
    estimated_tokens: int


@dataclass(frozen=True, slots=True)
class ContextSectionReport:
    """Observable size and inclusion data for one section."""

    name: str
    kind: str
    tier: str
    priority: int
    source: str
    chars: int
    estimated_tokens: int
    included: bool
    reason: str
    policy: str


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
                    "tier": section.tier,
                    "priority": section.priority,
                    "source": section.source,
                    "chars": section.chars,
                    "estimated_tokens": section.estimated_tokens,
                    "included": section.included,
                    "reason": section.reason,
                    "policy": section.policy,
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


class ContextBuilder:
    """Build model messages from identity, placeholders, and conversation."""

    def __init__(
        self,
        identity: str | None = None,
        runtime_environment: str | None = None,
        delegation_policy: str | None = DEFAULT_DELEGATION_POLICY,
        core_memory_provider: Callable[[], str] | None = None,
        conversation_summary_provider: Callable[[], str] | None = None,
        active_skills_provider: Callable[[], str] | None = None,
        skill_registry: SkillRegistry | None = None,
        budget: ContextBudget | None = None,
        workspace_provider: Any | None = None,
    ) -> None:
        self.identity = identity or (
            "You are MyAgent, a lightweight ReAct agent runtime for learning "
            "and interview practice. Be concise, helpful, and honest about "
            "current limitations."
        )
        self.runtime_environment = runtime_environment
        self.delegation_policy = delegation_policy
        self.core_memory_provider = core_memory_provider
        self.conversation_summary_provider = conversation_summary_provider
        self.active_skills_provider = active_skills_provider
        self.skill_registry = skill_registry
        self.budget = budget or ContextBudget()
        self.workspace_provider = workspace_provider
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
                kind=ContextItemKind.INSTRUCTION,
                policy=ContextRetentionPolicy.NEVER_DROP,
            ),
        ]
        workspace_sections = self._build_workspace_sections()
        sections.extend(workspace_sections)
        if self.runtime_environment:
            sections.append(
                ContextSection(
                    name="Runtime Environment",
                    content=self.runtime_environment,
                    priority=20,
                    tier=ContextTier.PROTECTED,
                    source="runtime:environment",
                    kind=ContextItemKind.INSTRUCTION,
                    policy=ContextRetentionPolicy.NEVER_DROP,
                )
            )
        core_memory = self.read_core_memory()
        if self.delegation_policy:
            sections.append(
                ContextSection(
                    name="Delegation Policy",
                    content=self.delegation_policy,
                    priority=25,
                    tier=ContextTier.PROTECTED,
                    source="agent:delegation_policy",
                    kind=ContextItemKind.INSTRUCTION,
                    policy=ContextRetentionPolicy.NEVER_DROP,
                )
            )
        if core_memory:
            sections.append(
                ContextSection(
                    name="Long-term Memory",
                    content=core_memory,
                    priority=30,
                    tier=ContextTier.HIGH,
                    source="memory:core",
                    kind=ContextItemKind.MEMORY_CORE,
                    policy=ContextRetentionPolicy.KEEP_IF_FITS,
                )
            )
        conversation_summary = self.read_conversation_summary()
        if conversation_summary:
            sections.append(
                ContextSection(
                    name="Conversation Summary",
                    content=conversation_summary,
                    priority=32,
                    tier=ContextTier.MEDIUM,
                    source="session:summary",
                    kind=ContextItemKind.SESSION_SUMMARY,
                    policy=ContextRetentionPolicy.KEEP_IF_FITS,
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
                    kind=ContextItemKind.ACTIVE_SKILL,
                    policy=ContextRetentionPolicy.DROP_IF_NEEDED,
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
                    kind=ContextItemKind.SKILL_SUMMARY,
                    policy=ContextRetentionPolicy.DROP_IF_NEEDED,
                )
            )
        return sections

    def build_system_prompt(self) -> str:
        """Build the system prompt from ordered sections."""
        items = self._items_from_sections(self.build_sections())
        selected_items, _, _ = self._select_system_items(items, reserved_tokens=0)
        return self._render_system_prompt(selected_items)

    def build_messages_with_report(
        self,
        current_message: InboundMessage,
        history: list[Message] | None = None,
    ) -> tuple[list[Message], ContextAssemblyReport]:
        """Build model messages and return a context assembly report."""
        raw_history = history or []
        current_tokens = _estimate_tokens(current_message.content, self.budget.chars_per_token)
        system_items = self._items_from_sections(self.build_sections())
        message_limited_history, message_limit_dropped = self._limit_history_by_message_count(
            raw_history
        )
        full_system_prompt = self._render_system_prompt(
            sorted(
                [item for item in system_items if item.content.strip()],
                key=lambda item: item.priority,
            )
        )
        estimated_tokens_before_budget = (
            _estimate_tokens(full_system_prompt, self.budget.chars_per_token)
            + sum(
                _estimate_tokens(str(message.get("content", "")), self.budget.chars_per_token)
                for message in message_limited_history
            )
            + current_tokens
        )
        history_reserved_tokens = self._history_reserved_tokens(message_limited_history)
        selected_items, section_reports, section_warnings = self._select_system_items(
            system_items,
            reserved_tokens=current_tokens + history_reserved_tokens,
        )
        system_prompt = self._render_system_prompt(selected_items)
        system_tokens = _estimate_tokens(system_prompt, self.budget.chars_per_token)
        remaining_history_tokens = None
        if self.budget.max_prompt_tokens is not None:
            remaining_history_tokens = max(
                self.budget.max_prompt_tokens - system_tokens - current_tokens,
                0,
            )
        selected_history, history_report, history_warnings = self.select_history(
            raw_history,
            max_history_tokens=remaining_history_tokens,
            message_limited_history=message_limited_history,
            dropped_by_message_limit=message_limit_dropped,
            reserved_history_tokens=history_reserved_tokens,
        )
        warnings = self._combine_warnings(
            estimated_tokens_before_budget=estimated_tokens_before_budget,
            section_warnings=section_warnings,
            history_warnings=history_warnings,
        )
        return [
            {"role": "system", "content": system_prompt},
            *selected_history,
            {"role": "user", "content": current_message.content},
        ], self._build_report(
            current_message=current_message,
            system_prompt=system_prompt,
            selected_history=selected_history,
            history_report=history_report,
            section_reports=section_reports,
            warnings=warnings,
            estimated_tokens_before_budget=estimated_tokens_before_budget,
        )

    def select_history(
        self,
        history: list[Message],
        max_history_tokens: int | None = None,
        message_limited_history: list[Message] | None = None,
        dropped_by_message_limit: int | None = None,
        reserved_history_tokens: int = 0,
    ) -> tuple[list[Message], ContextHistoryReport, list[str]]:
        """Select the history slice visible to the current model call."""
        max_messages = max(self.budget.max_history_messages, 0)
        if message_limited_history is None or dropped_by_message_limit is None:
            message_limited_history, dropped_by_message_limit = self._limit_history_by_message_count(
                history
            )
        if max_history_tokens is None:
            selected = list(message_limited_history)
            dropped_by_token_budget = 0
        else:
            selected, dropped_by_token_budget = self._limit_history_by_token_count(
                message_limited_history,
                max_history_tokens,
            )
        selected = _drop_invalid_leading_history(selected)
        dropped = len(history) - len(selected)
        estimated_tokens = sum(
            _estimate_tokens(str(message.get("content", "")), self.budget.chars_per_token)
            for message in selected
        )
        warnings = []
        if dropped_by_message_limit:
            warnings.append("history_trimmed")
        if dropped_by_token_budget:
            warnings.append("history_token_trimmed")
        return (
            selected,
            ContextHistoryReport(
                total_messages=len(history),
                included_messages=len(selected),
                dropped_messages=dropped,
                max_history_messages=max_messages,
                reserved_tokens=reserved_history_tokens,
                estimated_tokens=estimated_tokens,
                dropped_by_message_limit=dropped_by_message_limit,
                dropped_by_token_budget=dropped_by_token_budget,
            ),
            warnings,
        )

    def _items_from_sections(self, sections: list[ContextSection]) -> list[ContextItem]:
        """Convert public sections into internal budgetable items."""
        items = []
        for section in sections:
            content = section.content.strip()
            items.append(
                ContextItem(
                    id=f"{section.source}:{section.name}",
                    name=section.name,
                    kind=section.kind,
                    tier=section.tier,
                    priority=section.priority,
                    source=section.source,
                    content=content,
                    policy=section.policy,
                    estimated_tokens=_estimate_tokens(content, self.budget.chars_per_token),
                )
            )
        return items

    def _select_system_items(
        self,
        items: list[ContextItem],
        reserved_tokens: int,
    ) -> tuple[list[ContextItem], list[ContextSectionReport], list[str]]:
        """Select system context items under the configured prompt budget."""
        non_empty = [item for item in items if item.content.strip()]
        max_prompt_tokens = self.budget.max_prompt_tokens
        if max_prompt_tokens is None:
            selected_ids = {item.id for item in non_empty}
            return (
                sorted(non_empty, key=lambda item: item.priority),
                self._section_reports(items, selected_ids, {}),
                [],
            )

        protected = [
            item
            for item in non_empty
            if item.tier == ContextTier.PROTECTED or item.policy == ContextRetentionPolicy.NEVER_DROP
        ]
        selected: list[ContextItem] = list(protected)
        used_tokens = sum(item.estimated_tokens for item in selected) + reserved_tokens
        dropped_reasons: dict[str, str] = {}
        warnings: list[str] = []

        candidates = [
            item
            for item in non_empty
            if item.tier != ContextTier.PROTECTED
            and item.policy != ContextRetentionPolicy.NEVER_DROP
        ]
        for item in sorted(candidates, key=_budget_candidate_sort_key):
            if used_tokens + item.estimated_tokens <= max_prompt_tokens:
                selected.append(item)
                used_tokens += item.estimated_tokens
            else:
                dropped_reasons[item.id] = "budget_exceeded"

        if used_tokens > max_prompt_tokens:
            warnings.append("protected_context_over_budget")
        if dropped_reasons:
            warnings.append("section_dropped")
        selected_ids = {item.id for item in selected}
        return (
            sorted(selected, key=lambda item: item.priority),
            self._section_reports(items, selected_ids, dropped_reasons),
            warnings,
        )

    def _section_reports(
        self,
        items: list[ContextItem],
        selected_ids: set[str],
        dropped_reasons: dict[str, str],
    ) -> list[ContextSectionReport]:
        """Build section reports for both included and dropped items."""
        reports = []
        for item in sorted(items, key=lambda value: value.priority):
            has_content = bool(item.content.strip())
            included = item.id in selected_ids
            reason = "included" if included else dropped_reasons.get(item.id, "empty")
            if has_content and not included and reason == "empty":
                reason = "budget_exceeded"
            reports.append(
                ContextSectionReport(
                    name=item.name,
                    kind=item.kind.value,
                    tier=item.tier.value,
                    priority=item.priority,
                    source=item.source,
                    chars=len(item.content),
                    estimated_tokens=item.estimated_tokens,
                    included=included,
                    reason=reason,
                    policy=item.policy.value,
                )
            )
        return reports

    def _render_system_prompt(self, items: list[ContextItem]) -> str:
        """Render selected system items into a model system prompt."""
        return "\n\n---\n\n".join(
            f"# {item.name}\n\n{item.content}" for item in items if item.content.strip()
        )

    def _limit_history_by_message_count(self, history: list[Message]) -> tuple[list[Message], int]:
        """Apply the configured message-count history window."""
        max_messages = max(self.budget.max_history_messages, 0)
        dropped = max(len(history) - max_messages, 0)
        selected = history[-max_messages:] if max_messages else []
        return list(selected), dropped

    def _history_reserved_tokens(self, history: list[Message]) -> int:
        """Return the prompt budget reserved for session history."""
        if self.budget.max_prompt_tokens is None or not history:
            return 0
        ratio = min(max(self.budget.history_token_ratio, 0.0), 1.0)
        return int(self.budget.max_prompt_tokens * ratio)

    def _limit_history_by_token_count(
        self,
        history: list[Message],
        max_history_tokens: int,
    ) -> tuple[list[Message], int]:
        """Keep the newest history messages that fit the remaining token budget."""
        selected_reversed: list[Message] = []
        used_tokens = 0
        dropped = 0
        for message in reversed(history):
            tokens = _estimate_tokens(
                str(message.get("content", "")),
                self.budget.chars_per_token,
            )
            if used_tokens + tokens <= max_history_tokens:
                selected_reversed.append(message)
                used_tokens += tokens
            else:
                dropped += 1
        return list(reversed(selected_reversed)), dropped

    def _combine_warnings(
        self,
        estimated_tokens_before_budget: int,
        section_warnings: list[str],
        history_warnings: list[str],
    ) -> list[str]:
        """Return stable report warnings without duplicates."""
        warnings: list[str] = []
        if (
            self.budget.max_prompt_tokens is not None
            and estimated_tokens_before_budget > self.budget.max_prompt_tokens
        ):
            warnings.append("context_budget_exceeded")
        for warning in [*section_warnings, *history_warnings]:
            if warning not in warnings:
                warnings.append(warning)
        return warnings

    def _build_workspace_sections(self) -> list[ContextSection]:
        """Build workspace-derived sections if a workspace provider is configured."""
        if self.workspace_provider is None:
            return []
        sections: list[ContextSection] = []
        agent_principles = self.workspace_provider.load_file("AGENT.md").strip()
        if agent_principles:
            sections.append(
                ContextSection(
                    name="Agent Principles",
                    content=agent_principles,
                    priority=5,
                    tier=ContextTier.PROTECTED,
                    source="workspace:agent",
                    kind=ContextItemKind.WORKSPACE,
                    policy=ContextRetentionPolicy.NEVER_DROP,
                )
            )
        user_profile = self.workspace_provider.load_file("USER.md").strip()
        if user_profile:
            sections.append(
                ContextSection(
                    name="User Profile",
                    content=user_profile,
                    priority=7,
                    tier=ContextTier.PROTECTED,
                    source="workspace:user",
                    kind=ContextItemKind.WORKSPACE,
                    policy=ContextRetentionPolicy.NEVER_DROP,
                )
            )
        tool_guidelines = self.workspace_provider.load_file("TOOLS.md").strip()
        if tool_guidelines:
            sections.append(
                ContextSection(
                    name="Tool Guidelines",
                    content=tool_guidelines,
                    priority=35,
                    tier=ContextTier.MEDIUM,
                    source="workspace:tools",
                    kind=ContextItemKind.WORKSPACE,
                    policy=ContextRetentionPolicy.DROP_IF_NEEDED,
                )
            )
        return sections

    def read_core_memory(self) -> str:
        """Read always-visible long-term memory for the system prompt."""
        if self.core_memory_provider is None:
            return ""
        return self.core_memory_provider().strip()

    def read_conversation_summary(self) -> str:
        """Read compact session summary for the system prompt."""
        if self.conversation_summary_provider is None:
            return ""
        return self.conversation_summary_provider().strip()

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
        system_prompt: str,
        selected_history: list[Message],
        history_report: ContextHistoryReport,
        section_reports: list[ContextSectionReport],
        warnings: list[str],
        estimated_tokens_before_budget: int,
    ) -> ContextAssemblyReport:
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
            estimated_tokens_before_budget=estimated_tokens_before_budget,
            max_prompt_tokens=self.budget.max_prompt_tokens,
            message_count=len(messages),
            sections=section_reports,
            history=history_report,
            warnings=warnings,
        )


def _estimate_tokens(text: str, chars_per_token: int) -> int:
    divisor = max(chars_per_token, 1)
    return max((len(text) + divisor - 1) // divisor, 0)


def _budget_candidate_sort_key(item: ContextItem) -> tuple[int, int, str]:
    """Sort budget candidates by survival tier, then local priority."""
    tier_rank = {
        ContextTier.HIGH: 0,
        ContextTier.MEDIUM: 1,
        ContextTier.LOW: 2,
        ContextTier.EPHEMERAL: 3,
        ContextTier.PROTECTED: -1,
    }
    return (tier_rank.get(item.tier, 99), item.priority, item.name)


def _drop_invalid_leading_history(history: list[Message]) -> list[Message]:
    """Keep selected chat history in a valid user-starting shape."""
    selected = list(history)
    while selected and selected[0].get("role") != "user":
        selected.pop(0)
    return selected


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
