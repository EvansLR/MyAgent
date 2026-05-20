"""Context assembly for model calls."""

from typing import Any, Callable

from myagent.agent.context.sections import ContextSectionBuilder
from myagent.agent.context.selection import (
    drop_invalid_leading_history,
    estimate_tokens,
    render_system_prompt,
    select_history as select_context_history,
)
from myagent.agent.context.types import ContextBudget, ContextSection, Message
from myagent.bus import InboundMessage
from myagent.skills import SkillRegistry

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
    """Build model messages from system sections and conversation history."""

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

    def build_sections(self) -> list[ContextSection]:
        """Return system prompt sections in their model-facing order."""
        self._sync_section_builder()
        return self.section_builder.build_sections()

    def build_messages(
        self,
        current_message: InboundMessage,
        history: list[Message] | None = None,
    ) -> list[Message]:
        """Build model messages for one provider call."""
        selected_history = self.select_history(history or [])
        system_prompt = render_system_prompt(self.build_sections())
        return [
            {"role": "system", "content": system_prompt},
            *selected_history,
            {"role": "user", "content": current_message.content},
        ]

    def select_history(
        self,
        history: list[Message],
        max_history_tokens: int | None = None,
    ) -> list[Message]:
        """Select the history slice visible to the current model call."""
        return select_context_history(
            history,
            self.budget,
            max_history_tokens=max_history_tokens,
        )

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
