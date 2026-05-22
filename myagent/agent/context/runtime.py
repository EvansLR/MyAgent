"""Context runtime assembly for AgentLoop."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from myagent.agent.context.builder import ContextBuilder
from myagent.agent.context.summary import (
    ConversationSummarizer,
    ConversationSummaryConfig,
)
from myagent.agent.runtime.env import format_runtime_environment
from myagent.agent.runtime.session_history import AgentSessionHistory
from myagent.agent.runtime.skill_state import AgentSkillState
from myagent.memory.services import AgentMemoryServices
from myagent.profile import ProfileLoader
from myagent.providers.base import BaseProvider
from myagent.skills import SkillRegistry
from myagent.tools.registry import ToolRegistry


@dataclass(slots=True)
class AgentContextRuntime:
    """Own context construction, session summary, and active skill state."""

    builder: ContextBuilder
    session_history: AgentSessionHistory
    skill_state: AgentSkillState
    skill_registry: SkillRegistry
    profile_loader: ProfileLoader
    summarizer: ConversationSummarizer
    summary_config: ConversationSummaryConfig

    @classmethod
    def create(
        cls,
        provider: BaseProvider,
        *,
        memory: AgentMemoryServices,
        builder: ContextBuilder | None = None,
        skill_registry: SkillRegistry | None = None,
        workspace_root: Path | str | None = None,
        profile_loader: ProfileLoader | None = None,
        summary_config: ConversationSummaryConfig | None = None,
    ) -> "AgentContextRuntime":
        skills = skill_registry or SkillRegistry.from_directory()
        profile = profile_loader or ProfileLoader()
        config = summary_config or ConversationSummaryConfig()
        summarizer = ConversationSummarizer(provider, config)
        skill_state = AgentSkillState()
        session_history = AgentSessionHistory(
            summarizer,
            config,
            memory.extractor,
        )
        context_builder = builder or ContextBuilder(
            runtime_environment_provider=lambda: format_runtime_environment(workspace_root),
            always_memory_provider=memory.store.read_always_memory,
            now_memory_provider=memory.store.read_now_memory,
            conversation_summary_provider=session_history.current_summary_context,
            active_skills_provider=skill_state.current_active_skills_context,
            skill_registry=skills,
            profile_provider=profile,
        )
        cls._fill_missing_builder_providers(
            context_builder,
            memory=memory,
            session_history=session_history,
            skill_state=skill_state,
            skill_registry=skills,
            profile_loader=profile,
        )
        budget = context_builder.budget
        summarizer.chars_per_token = budget.chars_per_token
        memory.apply_compression_budget(
            token_limit=budget.memory_token_limit,
            max_rounds=budget.max_compression_rounds,
            chars_per_token=budget.chars_per_token,
        )
        return cls(
            builder=context_builder,
            session_history=session_history,
            skill_state=skill_state,
            skill_registry=skills,
            profile_loader=profile,
            summarizer=summarizer,
            summary_config=config,
        )

    @staticmethod
    def _fill_missing_builder_providers(
        builder: ContextBuilder,
        *,
        memory: AgentMemoryServices,
        session_history: AgentSessionHistory,
        skill_state: AgentSkillState,
        skill_registry: SkillRegistry,
        profile_loader: ProfileLoader,
    ) -> None:
        if builder.always_memory_provider is None:
            builder.always_memory_provider = memory.store.read_always_memory
        if builder.now_memory_provider is None:
            builder.now_memory_provider = memory.store.read_now_memory
        if builder.conversation_summary_provider is None:
            builder.conversation_summary_provider = session_history.current_summary_context
        if builder.active_skills_provider is None:
            builder.active_skills_provider = skill_state.current_active_skills_context
        if builder.skill_registry is None:
            builder.skill_registry = skill_registry
        if builder.profile_provider is None:
            builder.profile_provider = profile_loader

    def register_skill_tools(self, registry: ToolRegistry) -> None:
        """Expose context-related skill loading tools when skills are available."""
        if not self.skill_registry.list_skills() or registry.has("skill_get"):
            return
        from myagent.tools import SkillGetTool

        registry.register(
            SkillGetTool(
                self.skill_registry,
                active_skill_callback=self.skill_state.set_active_skill,
            )
        )
