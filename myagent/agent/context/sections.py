"""System prompt section assembly for context building."""

from __future__ import annotations

from typing import Any, Callable

from myagent.agent.context.types import (
    ContextItemKind,
    ContextRetention,
    ContextSection,
)
from myagent.skills import SkillRegistry


class ContextSectionBuilder:
    """Build ordered model-facing system prompt sections."""

    def __init__(
        self,
        *,
        identity: str,
        runtime_environment: str | None = None,
        runtime_environment_provider: Callable[[], str] | None = None,
        delegation_policy: str | None = None,
        always_memory_provider: Callable[[], str] | None = None,
        now_memory_provider: Callable[[], str] | None = None,
        conversation_summary_provider: Callable[[], str] | None = None,
        active_skills_provider: Callable[[], str] | None = None,
        skill_registry: SkillRegistry | None = None,
        profile_provider: Any | None = None,
    ) -> None:
        self.identity = identity
        self.runtime_environment = runtime_environment
        self.runtime_environment_provider = runtime_environment_provider
        self.delegation_policy = delegation_policy
        self.always_memory_provider = always_memory_provider
        self.now_memory_provider = now_memory_provider
        self.conversation_summary_provider = conversation_summary_provider
        self.active_skills_provider = active_skills_provider
        self.skill_registry = skill_registry
        self.profile_provider = profile_provider

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
        sections.extend(self._build_profile_sections())
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
