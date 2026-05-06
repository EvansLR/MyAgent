"""Context assembly for model calls."""

from dataclasses import dataclass
from typing import Any

from myagent.bus import InboundMessage

Message = dict[str, Any]


@dataclass(frozen=True, slots=True)
class ContextSection:
    """One section of the system prompt."""

    name: str
    content: str
    priority: int = 100


class ContextBuilder:
    """Build model messages from identity, placeholders, and conversation."""

    def __init__(self, identity: str | None = None) -> None:
        self.identity = identity or (
            "You are MyAgent, a lightweight ReAct agent runtime for learning "
            "and interview practice. Be concise, helpful, and honest about "
            "current limitations."
        )

    def build_sections(self) -> list[ContextSection]:
        """Return system prompt sections in first-stage priority order."""
        return [
            ContextSection(name="Identity", content=self.identity, priority=1),
        ]

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
        return [
            {"role": "system", "content": self.build_system_prompt()},
            *(history or []),
            {"role": "user", "content": current_message.content},
        ]
