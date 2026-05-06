"""OpenAI-compatible chat completions provider."""

from typing import Any

from openai import AsyncOpenAI

from myagent.agent.context import Message
from myagent.config import Settings


class OpenAICompatibleProvider:
    """Generate replies using an OpenAI-compatible chat completions API."""

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        if not settings.api_key:
            raise ValueError("OpenAICompatibleProvider requires an API key.")

        self.settings = settings
        self.client = client or AsyncOpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
        )

    async def generate(self, messages: list[Message]) -> str:
        """Generate a text response for model messages."""
        last_error: Exception | None = None
        for _ in range(self.settings.provider_retries):
            try:
                completion = await self.client.chat.completions.create(
                    model=self.settings.model,
                    messages=messages,
                )
                content = completion.choices[0].message.content
                return content or ""
            except Exception as exc:  # pragma: no cover - exact SDK errors vary by backend
                last_error = exc
        raise RuntimeError("OpenAI-compatible provider failed after retries.") from last_error
