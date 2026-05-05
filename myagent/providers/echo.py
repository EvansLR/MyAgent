"""A no-network provider used to validate the runtime flow."""

from myagent.bus import InboundMessage


class EchoProvider:
    """Return a deterministic response for local development."""

    async def generate(self, message: InboundMessage) -> str:
        """Return a simple echo response."""
        return f"Echo: {message.content}"
