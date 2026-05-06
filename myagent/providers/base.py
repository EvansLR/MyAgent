"""Common provider interface."""

from typing import Protocol

from myagent.agent.context import Message


class BaseProvider(Protocol):
    """Minimal provider contract used by the first-stage AgentLoop."""

    async def generate(self, messages: list[Message]) -> str:
        """Generate a text response for model messages."""
        ...
