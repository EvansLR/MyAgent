"""Common provider interface."""

from typing import Protocol

from myagent.bus import InboundMessage


class BaseProvider(Protocol):
    """Minimal provider contract used by the first-stage AgentLoop."""

    async def generate(self, message: InboundMessage) -> str:
        """Generate a text response for one inbound message."""
        ...
