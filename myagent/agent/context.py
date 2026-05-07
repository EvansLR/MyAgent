"""Context assembly for model calls."""

from dataclasses import dataclass
from typing import Any, Callable

from myagent.bus import InboundMessage
from myagent.memory import MemoryEntry, MemoryRecall
from myagent.skills import SkillRegistry

Message = dict[str, Any]


@dataclass(frozen=True, slots=True)
class ContextSection:
    """One section of the system prompt."""

    name: str
    content: str
    priority: int = 100


class ContextBuilder:
    """Build model messages from identity, placeholders, and conversation."""

    def __init__(
        self,
        identity: str | None = None,
        memory_recall: MemoryRecall | None = None,
        core_memory_provider: Callable[[], str] | None = None,
        skill_registry: SkillRegistry | None = None,
    ) -> None:
        self.identity = identity or (
            "You are MyAgent, a lightweight ReAct agent runtime for learning "
            "and interview practice. Be concise, helpful, and honest about "
            "current limitations."
        )
        self.memory_recall = memory_recall
        self.core_memory_provider = core_memory_provider
        self.skill_registry = skill_registry

    def build_sections(self, memories: list[MemoryEntry] | None = None) -> list[ContextSection]:
        """Return system prompt sections in first-stage priority order."""
        sections = [
            ContextSection(name="Identity", content=self.identity, priority=1),
        ]
        core_memory = self.read_core_memory()
        if core_memory:
            sections.append(
                ContextSection(
                    name="Core Memory",
                    content=core_memory,
                    priority=10,
                )
            )
        if memories:
            sections.append(
                ContextSection(
                    name="Memory",
                    content="\n".join(f"- {memory.content}" for memory in memories),
                    priority=20,
                )
            )
        skills_content = self.format_skills()
        if skills_content:
            sections.append(
                ContextSection(
                    name="Available Skills",
                    content=skills_content,
                    priority=30,
                )
            )
        return sections

    def build_system_prompt(self, memories: list[MemoryEntry] | None = None) -> str:
        """Build the system prompt from ordered sections."""
        sections = sorted(self.build_sections(memories), key=lambda section: section.priority)
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
        memories = self.recall_memory(current_message.content)
        return [
            {"role": "system", "content": self.build_system_prompt(memories)},
            *(history or []),
            {"role": "user", "content": current_message.content},
        ]

    def recall_memory(self, query: str) -> list[MemoryEntry]:
        """Recall memory entries for a user query."""
        if self.memory_recall is None:
            return []
        return self.memory_recall.recall(query)

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
