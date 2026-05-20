"""Context assembly for model calls."""

from typing import Any, Callable

from myagent.bus import InboundMessage
from myagent.skills import SkillRegistry
from myagent.agent.context_types import (
    ContextAssemblyReport,
    ContextBudget,
    ContextHistoryReport,
    ContextItem,
    ContextItemKind,
    ContextRetention,
    ContextSection,
    ContextSectionReport,
    Message,
)
from myagent.agent.runtime_env import format_runtime_environment

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


class ContextBuilder:
    """Build model messages from identity, placeholders, and conversation."""

    def __init__(
        self,
        identity: str | None = None,
        runtime_environment: str | None = None,
        runtime_environment_provider: Callable[[], str] | None = None,
        delegation_policy: str | None = DEFAULT_DELEGATION_POLICY,
        always_memory_provider: Callable[[], str] | None = None,
        now_memory_provider: Callable[[], str] | None = None,
        conversation_summary_provider: Callable[[], str] | None = None,
        active_skills_provider: Callable[[], str] | None = None,
        skill_registry: SkillRegistry | None = None,
        budget: ContextBudget | None = None,
        profile_provider: Any | None = None,
    ) -> None:
        self.identity = identity or (
            "You are MyAgent, a lightweight ReAct agent runtime for learning "
            "and interview practice. Be concise, helpful, and honest about "
            "current limitations."
        )
        self.runtime_environment = runtime_environment
        self.runtime_environment_provider = runtime_environment_provider
        self.delegation_policy = delegation_policy
        self.always_memory_provider = always_memory_provider
        self.now_memory_provider = now_memory_provider
        self.conversation_summary_provider = conversation_summary_provider
        self.active_skills_provider = active_skills_provider
        self.skill_registry = skill_registry
        self.budget = budget or ContextBudget()
        self.profile_provider = profile_provider
        self.last_report: ContextAssemblyReport | None = None

    def build_sections(self) -> list[ContextSection]:
        """Return system prompt sections in their model-facing order."""
        sections = [
            ContextSection(
                name="Identity",
                content=self.identity,
                source="identity",
                kind=ContextItemKind.INSTRUCTION,
                retention=ContextRetention.REQUIRED,
            ),
        ]
        profile_sections = self._build_profile_sections()
        sections.extend(profile_sections)
        runtime_environment = self.read_runtime_environment()
        if runtime_environment:
            sections.append(
                ContextSection(
                    name="Runtime Environment",
                    content=runtime_environment,
                    source="runtime:environment",
                    kind=ContextItemKind.INSTRUCTION,
                    retention=ContextRetention.REQUIRED,
                )
            )
        if self.delegation_policy:
            sections.append(
                ContextSection(
                    name="Delegation Policy",
                    content=self.delegation_policy,
                    source="agent:delegation_policy",
                    kind=ContextItemKind.INSTRUCTION,
                    retention=ContextRetention.REQUIRED,
                )
            )
        always_memory = self.read_always_memory()
        now_memory = self.read_now_memory()
        if always_memory:
            sections.append(
                ContextSection(
                    name="Always Memory",
                    content=always_memory,
                    source="memory:always",
                    kind=ContextItemKind.MEMORY_CORE,
                    retention=ContextRetention.CORE,
                )
            )
        if now_memory:
            sections.append(
                ContextSection(
                    name="Now Memory",
                    content=now_memory,
                    source="memory:now",
                    kind=ContextItemKind.MEMORY_CORE,
                    retention=ContextRetention.CONTEXT,
                )
            )
        conversation_summary = self.read_conversation_summary()
        if conversation_summary:
            sections.append(
                ContextSection(
                    name="Conversation Summary",
                    content=conversation_summary,
                    source="session:summary",
                    kind=ContextItemKind.SESSION_SUMMARY,
                    retention=ContextRetention.CONTEXT,
                )
            )
        active_skills = self.read_active_skills()
        if active_skills:
            sections.append(
                ContextSection(
                    name="Active Skills",
                    content=active_skills,
                    source="skills:active",
                    kind=ContextItemKind.ACTIVE_SKILL,
                    retention=ContextRetention.OPTIONAL,
                )
            )
        skills_content = self.format_skills()
        if skills_content:
            sections.append(
                ContextSection(
                    name="Available Skills",
                    content=skills_content,
                    source="skills:summary",
                    kind=ContextItemKind.SKILL_SUMMARY,
                    retention=ContextRetention.OPTIONAL,
                )
            )
        return sections

    def build_messages_with_report(
        self,
        current_message: InboundMessage,
        history: list[Message] | None = None,
    ) -> tuple[list[Message], ContextAssemblyReport]:
        """Build model messages and return a context assembly report."""
        raw_history = history or []
        current_tokens = _estimate_tokens(current_message.content, self.budget.chars_per_token)
        system_items = self._items_from_sections(self.build_sections())
        full_system_prompt = self._render_system_prompt(
            [item for item in system_items if item.content.strip()]
        )
        estimated_tokens_before_budget = (
            _estimate_tokens(full_system_prompt, self.budget.chars_per_token)
            + sum(
                _estimate_tokens(str(message.get("content", "")), self.budget.chars_per_token)
                for message in raw_history
            )
            + current_tokens
        )
        history_reserved_tokens = self._history_reserved_tokens(raw_history)
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
        reserved_history_tokens: int = 0,
    ) -> tuple[list[Message], ContextHistoryReport, list[str]]:
        """Select the history slice visible to the current model call."""
        if max_history_tokens is None:
            selected = list(history)
            dropped_by_token_budget = 0
        else:
            selected, dropped_by_token_budget = self._limit_history_by_token_count(
                history,
                max_history_tokens,
            )
        selected, dropped_by_message_limit = self._limit_history_by_message_count(selected)
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
                max_history_messages=self.budget.max_history_messages or 0,
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
        for order, section in enumerate(sections):
            content = section.content.strip()
            items.append(
                ContextItem(
                    id=f"{section.source}:{section.name}",
                    name=section.name,
                    kind=section.kind,
                    retention=section.retention,
                    order=order,
                    source=section.source,
                    content=content,
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
                sorted(non_empty, key=lambda item: item.order),
                self._section_reports(items, selected_ids, {}),
                [],
            )

        required = [item for item in non_empty if item.retention == ContextRetention.REQUIRED]
        selected: list[ContextItem] = list(required)
        used_tokens = sum(item.estimated_tokens for item in selected) + reserved_tokens
        dropped_reasons: dict[str, str] = {}
        warnings: list[str] = []

        candidates = [item for item in non_empty if item.retention != ContextRetention.REQUIRED]
        for item in sorted(candidates, key=_retention_sort_key):
            if used_tokens + item.estimated_tokens <= max_prompt_tokens:
                selected.append(item)
                used_tokens += item.estimated_tokens
            else:
                dropped_reasons[item.id] = "budget_exceeded"

        if used_tokens > max_prompt_tokens:
            warnings.append("required_context_over_budget")
        if dropped_reasons:
            warnings.append("section_dropped")
        selected_ids = {item.id for item in selected}
        return (
            sorted(selected, key=lambda item: item.order),
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
        for item in sorted(items, key=lambda value: value.order):
            has_content = bool(item.content.strip())
            included = item.id in selected_ids
            reason = "included" if included else dropped_reasons.get(item.id, "empty")
            if has_content and not included and reason == "empty":
                reason = "budget_exceeded"
            reports.append(
                ContextSectionReport(
                    name=item.name,
                    kind=item.kind.value,
                    retention=item.retention.value,
                    source=item.source,
                    chars=len(item.content),
                    estimated_tokens=item.estimated_tokens,
                    included=included,
                    reason=reason,
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
        if self.budget.max_history_messages is None:
            return list(history), 0
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

    def _build_profile_sections(self) -> list[ContextSection]:
        """Build agent profile sections if a profile provider is configured."""
        if self.profile_provider is None:
            return []
        sections: list[ContextSection] = []
        agent_principles = self.profile_provider.load_file("AGENT.md").strip()
        if agent_principles:
            sections.append(
                ContextSection(
                    name="Agent Instructions",
                    content=agent_principles,
                    source="profile:agent",
                    kind=ContextItemKind.PROFILE,
                    retention=ContextRetention.REQUIRED,
                )
            )
        user_profile = self.profile_provider.load_file("USER.md").strip()
        if user_profile:
            sections.append(
                ContextSection(
                    name="User Profile",
                    content=user_profile,
                    source="profile:user",
                    kind=ContextItemKind.PROFILE,
                    retention=ContextRetention.REQUIRED,
                )
            )
        tool_guidelines = self.profile_provider.load_file("TOOLS.md").strip()
        if tool_guidelines:
            sections.append(
                ContextSection(
                    name="Tool Guidelines",
                    content=tool_guidelines,
                    source="profile:tools",
                    kind=ContextItemKind.PROFILE,
                    retention=ContextRetention.OPTIONAL,
                )
            )
        return sections

    def read_runtime_environment(self) -> str:
        """Read current runtime facts for the system prompt."""
        if self.runtime_environment_provider is not None:
            return self.runtime_environment_provider().strip()
        return (self.runtime_environment or "").strip()

    def read_always_memory(self) -> str:
        """Read stable compact memory for the system prompt."""
        if self.always_memory_provider is None:
            return ""
        return self.always_memory_provider().strip()

    def read_now_memory(self) -> str:
        """Read compact current working memory for the system prompt."""
        if self.now_memory_provider is None:
            return ""
        return self.now_memory_provider().strip()

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


def _retention_sort_key(item: ContextItem) -> tuple[int, int, str]:
    """Sort candidates by survival strength, then model-facing order."""
    retention_rank = {
        ContextRetention.CORE: 0,
        ContextRetention.CONTEXT: 1,
        ContextRetention.OPTIONAL: 2,
    }
    return (retention_rank.get(item.retention, 99), item.order, item.name)


def _drop_invalid_leading_history(history: list[Message]) -> list[Message]:
    """Keep selected chat history in a valid user-starting shape."""
    selected = list(history)
    while selected and selected[0].get("role") != "user":
        selected.pop(0)
    return selected
