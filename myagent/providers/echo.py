"""A no-network provider used to validate the runtime flow."""

from myagent.providers.base import Message, ProviderResponse


class EchoProvider:
    """Return a deterministic response for local development."""

    async def generate(self, messages: list[Message]) -> str:
        """Return a simple echo response."""
        for message in reversed(messages):
            if message.get("role") == "user":
                return f"Echo: {message.get('content', '')}"
        return "Echo:"

    async def generate_response(
        self,
        messages: list[Message],
        tools: list[dict[str, object]] | None = None,
    ) -> ProviderResponse:
        """Return a structured echo response with no tool calls."""
        return ProviderResponse(content=await self.generate(messages))
