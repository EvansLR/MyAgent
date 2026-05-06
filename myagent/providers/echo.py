"""A no-network provider used to validate the runtime flow."""

from myagent.agent.context import Message


class EchoProvider:
    """Return a deterministic response for local development."""

    async def generate(self, messages: list[Message]) -> str:
        """Return a simple echo response."""
        for message in reversed(messages):
            if message.get("role") == "user":
                return f"Echo: {message.get('content', '')}"
        return "Echo:"
