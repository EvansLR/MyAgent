"""Context assembly for model calls."""

from typing import Any, Callable

from myagent.bus import InboundMessage
from myagent.skills import SkillRegistry
from myagent.agent.context.sections import ContextSectionBuilder
from myagent.agent.context.selection import (
    build_report,
    combine_warnings,
    drop_invalid_leading_history,
    estimate_tokens,
    items_from_sections,
    render_system_prompt,
    section_reports,
    select_history as select_context_history,
    select_system_items,
)
from myagent.agent.context.types import (
    ContextAssemblyReport,
    ContextBudget,
    ContextHistoryReport,
    ContextItem,
    ContextSection,
    ContextSectionReport,
    Message,
)

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
        self.section_builder = ContextSectionBuilder(
            identity=self.identity,
            runtime_environment=self.runtime_environment,
            runtime_environment_provider=self.runtime_environment_provider,
            delegation_policy=self.delegation_policy,
            always_memory_provider=self.always_memory_provider,
            now_memory_provider=self.now_memory_provider,
            conversation_summary_provider=self.conversation_summary_provider,
            active_skills_provider=self.active_skills_provider,
            skill_registry=self.skill_registry,
            profile_provider=self.profile_provider,
        )
        self.last_report: ContextAssemblyReport | None = None

    def build_sections(self) -> list[ContextSection]:
        """Return system prompt sections in their model-facing order."""
        self._sync_section_builder()
        return self.section_builder.build_sections()

    def _sync_section_builder(self) -> None:
        """Keep delegated section assembly aligned with public provider attrs."""
        self.section_builder.identity = self.identity
        self.section_builder.runtime_environment = self.runtime_environment
        self.section_builder.runtime_environment_provider = self.runtime_environment_provider
        self.section_builder.delegation_policy = self.delegation_policy
        self.section_builder.always_memory_provider = self.always_memory_provider
        self.section_builder.now_memory_provider = self.now_memory_provider
        self.section_builder.conversation_summary_provider = self.conversation_summary_provider
        self.section_builder.active_skills_provider = self.active_skills_provider
        self.section_builder.skill_registry = self.skill_registry
        self.section_builder.profile_provider = self.profile_provider

    def build_messages_with_report(
        self,
        current_message: InboundMessage,
        history: list[Message] | None = None,
    ) -> tuple[list[Message], ContextAssemblyReport]:
        """Build model messages and return a context assembly report."""
        raw_history = history or []
        current_tokens = estimate_tokens(current_message.content, self.budget.chars_per_token)
        system_items = self._items_from_sections(self.build_sections())
        full_system_prompt = self._render_system_prompt(
            [item for item in system_items if item.content.strip()]
        )
        estimated_tokens_before_budget = (
            estimate_tokens(full_system_prompt, self.budget.chars_per_token)
            + sum(
                estimate_tokens(str(message.get("content", "")), self.budget.chars_per_token)
                for message in raw_history
            )
            + current_tokens
        )
        selected_items, section_reports, section_warnings = self._select_system_items(
            system_items,
            reserved_tokens=0,
        )
        system_prompt = self._render_system_prompt(selected_items)
        selected_history, history_report, history_warnings = self.select_history(
            raw_history,
            max_history_tokens=None,
            reserved_history_tokens=0,
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
        ], build_report(
            current_message=current_message,
            system_prompt=system_prompt,
            selected_history=selected_history,
            history_report=history_report,
            section_reports=section_reports,
            warnings=warnings,
            estimated_tokens_before_budget=estimated_tokens_before_budget,
            budget=self.budget,
        )

    def select_history(
        self,
        history: list[Message],
        max_history_tokens: int | None = None,
        reserved_history_tokens: int = 0,
    ) -> tuple[list[Message], ContextHistoryReport, list[str]]:
        """Select the history slice visible to the current model call."""
        return select_context_history(
            history,
            self.budget,
            max_history_tokens=max_history_tokens,
            reserved_history_tokens=reserved_history_tokens,
        )

    def _items_from_sections(self, sections: list[ContextSection]) -> list[ContextItem]:
        """Convert public sections into internal budgetable items."""
        return items_from_sections(sections, self.budget)

    def _select_system_items(
        self,
        items: list[ContextItem],
        reserved_tokens: int,
    ) -> tuple[list[ContextItem], list[ContextSectionReport], list[str]]:
        """Return non-empty system context items without prompt-time competition."""
        return select_system_items(items)

    def _section_reports(
        self,
        items: list[ContextItem],
        selected_ids: set[str],
        dropped_reasons: dict[str, str],
    ) -> list[ContextSectionReport]:
        """Build section reports for both included and dropped items."""
        return section_reports(items, selected_ids, dropped_reasons)

    def _render_system_prompt(self, items: list[ContextItem]) -> str:
        """Render selected system items into a model system prompt."""
        return render_system_prompt(items)

    def _limit_history_by_message_count(self, history: list[Message]) -> tuple[list[Message], int]:
        """Apply the configured message-count history window."""
        selected, report, _ = select_context_history(history, self.budget)
        return selected, report.dropped_by_message_limit

    def _limit_history_by_token_count(
        self,
        history: list[Message],
        max_history_tokens: int,
    ) -> tuple[list[Message], int]:
        """Keep the newest history messages that fit the remaining token budget."""
        selected, report, _ = select_context_history(
            history,
            self.budget,
            max_history_tokens=max_history_tokens,
        )
        return selected, report.dropped_by_token_budget

    def _combine_warnings(
        self,
        estimated_tokens_before_budget: int,
        section_warnings: list[str],
        history_warnings: list[str],
    ) -> list[str]:
        """Return stable report warnings without duplicates."""
        return combine_warnings(
            self.budget,
            estimated_tokens_before_budget,
            section_warnings,
            history_warnings,
        )

    def read_runtime_environment(self) -> str:
        """Read current runtime facts for the system prompt."""
        return self.section_builder.read_runtime_environment()

    def read_always_memory(self) -> str:
        """Read stable compact memory for the system prompt."""
        return self.section_builder.read_always_memory()

    def read_now_memory(self) -> str:
        """Read compact current working memory for the system prompt."""
        return self.section_builder.read_now_memory()

    def read_conversation_summary(self) -> str:
        """Read compact session summary for the system prompt."""
        return self.section_builder.read_conversation_summary()

    def read_active_skills(self) -> str:
        """Read compact current-turn active skill context for the system prompt."""
        return self.section_builder.read_active_skills()

    def format_skills(self) -> str:
        """Format available skills for the system prompt."""
        return self.section_builder.format_skills()

_estimate_tokens = estimate_tokens


def _drop_invalid_leading_history(history: list[Message]) -> list[Message]:
    """Keep selected chat history in a valid user-starting shape."""
    return drop_invalid_leading_history(history)
