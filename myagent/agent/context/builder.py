"""Context assembly for model calls."""

from typing import Any, Callable

from myagent.agent.context.sections import (
    ContextSectionBuilder,
    render_system_prompt,
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
        resolved_identity = identity or (
            "You are MyAgent, a lightweight ReAct agent runtime for learning "
            "and interview practice. Be concise, helpful, and honest about "
            "current limitations."
        )
        self.budget = budget or ContextBudget()
        self.section_builder = ContextSectionBuilder(
            identity=resolved_identity,
            runtime_environment=runtime_environment,
            runtime_environment_provider=runtime_environment_provider,
            delegation_policy=delegation_policy,
            always_memory_provider=always_memory_provider,
            now_memory_provider=now_memory_provider,
            conversation_summary_provider=conversation_summary_provider,
            active_skills_provider=active_skills_provider,
            skill_registry=skill_registry,
            profile_provider=profile_provider,
        )

    def build_sections(self) -> list[ContextSection]:
        """Return system prompt sections in their model-facing order."""
        return self.section_builder.build_sections()

    def build_messages(
        self,
        current_message: InboundMessage,
        history: list[Message] | None = None,
    ) -> list[Message]:
        """Build model messages for one provider call."""
        system_prompt = render_system_prompt(self.build_sections())
        return [
            {"role": "system", "content": system_prompt},
            *(history or []),
            {"role": "user", "content": current_message.content},
        ]

    @property
    def identity(self) -> str:
        return self.section_builder.identity

    @identity.setter
    def identity(self, value: str) -> None:
        self.section_builder.identity = value

    @property
    def runtime_environment(self) -> str | None:
        return self.section_builder.runtime_environment

    @runtime_environment.setter
    def runtime_environment(self, value: str | None) -> None:
        self.section_builder.runtime_environment = value

    @property
    def runtime_environment_provider(self) -> Callable[[], str] | None:
        return self.section_builder.runtime_environment_provider

    @runtime_environment_provider.setter
    def runtime_environment_provider(self, value: Callable[[], str] | None) -> None:
        self.section_builder.runtime_environment_provider = value

    @property
    def delegation_policy(self) -> str | None:
        return self.section_builder.delegation_policy

    @delegation_policy.setter
    def delegation_policy(self, value: str | None) -> None:
        self.section_builder.delegation_policy = value

    @property
    def always_memory_provider(self) -> Callable[[], str] | None:
        return self.section_builder.always_memory_provider

    @always_memory_provider.setter
    def always_memory_provider(self, value: Callable[[], str] | None) -> None:
        self.section_builder.always_memory_provider = value

    @property
    def now_memory_provider(self) -> Callable[[], str] | None:
        return self.section_builder.now_memory_provider

    @now_memory_provider.setter
    def now_memory_provider(self, value: Callable[[], str] | None) -> None:
        self.section_builder.now_memory_provider = value

    @property
    def conversation_summary_provider(self) -> Callable[[], str] | None:
        return self.section_builder.conversation_summary_provider

    @conversation_summary_provider.setter
    def conversation_summary_provider(self, value: Callable[[], str] | None) -> None:
        self.section_builder.conversation_summary_provider = value

    @property
    def active_skills_provider(self) -> Callable[[], str] | None:
        return self.section_builder.active_skills_provider

    @active_skills_provider.setter
    def active_skills_provider(self, value: Callable[[], str] | None) -> None:
        self.section_builder.active_skills_provider = value

    @property
    def skill_registry(self) -> SkillRegistry | None:
        return self.section_builder.skill_registry

    @skill_registry.setter
    def skill_registry(self, value: SkillRegistry | None) -> None:
        self.section_builder.skill_registry = value

    @property
    def profile_provider(self) -> Any | None:
        return self.section_builder.profile_provider

    @profile_provider.setter
    def profile_provider(self, value: Any | None) -> None:
        self.section_builder.profile_provider = value

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
