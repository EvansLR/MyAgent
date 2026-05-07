"""Common provider interface."""

from dataclasses import dataclass, field
from typing import Any, Protocol

Message = dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A tool call requested by a provider response."""

    id: str
    name: str
    arguments: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    """Structured provider response used by tool-capable agent loops."""

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    extra_message_fields: dict[str, object] = field(default_factory=dict)


class BaseProvider(Protocol):
    """Minimal provider contract used by the first-stage AgentLoop."""

    async def generate(self, messages: list[Message]) -> str:
        """Generate a text response for model messages."""
        ...

    async def generate_response(
        self,
        messages: list[Message],
        tools: list[dict[str, object]] | None = None,
    ) -> ProviderResponse:
        """Generate a structured response that may include tool calls."""
        ...
