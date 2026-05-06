"""OpenAI-compatible chat completions provider."""

import json
from typing import Any

from openai import AsyncOpenAI

from myagent.agent.context import Message
from myagent.config import Settings
from myagent.providers.base import ProviderResponse, ToolCall


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
        response = await self.generate_response(messages)
        return response.content

    async def generate_response(
        self,
        messages: list[Message],
        tools: list[dict[str, object]] | None = None,
    ) -> ProviderResponse:
        """Generate a structured response, including tool calls when requested."""
        last_error: Exception | None = None
        for _ in range(self.settings.provider_retries):
            try:
                kwargs: dict[str, Any] = {
                    "model": self.settings.model,
                    "messages": messages,
                }
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"

                completion = await self.client.chat.completions.create(**kwargs)
                message = completion.choices[0].message
                return ProviderResponse(
                    content=message.content or "",
                    tool_calls=_parse_tool_calls(getattr(message, "tool_calls", None)),
                    extra_message_fields=_extra_message_fields(message),
                )
            except Exception as exc:  # pragma: no cover - exact SDK errors vary by backend
                last_error = exc
        raise RuntimeError("OpenAI-compatible provider failed after retries.") from last_error


def _parse_tool_calls(raw_tool_calls: Any) -> list[ToolCall]:
    """Convert SDK tool call objects into MyAgent's small ToolCall model."""
    if not raw_tool_calls:
        return []

    tool_calls: list[ToolCall] = []
    for raw in raw_tool_calls:
        function = getattr(raw, "function", None)
        if function is None:
            continue
        name = getattr(function, "name", "")
        arguments_text = getattr(function, "arguments", "{}") or "{}"
        try:
            arguments = json.loads(arguments_text)
        except json.JSONDecodeError:
            arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}
        tool_calls.append(
            ToolCall(
                id=getattr(raw, "id", ""),
                name=name,
                arguments=arguments,
            )
        )
    return tool_calls


def _extra_message_fields(message: Any) -> dict[str, object]:
    """Preserve provider-specific assistant fields required by some backends."""
    fields: dict[str, object] = {}
    reasoning_content = getattr(message, "reasoning_content", None)
    if reasoning_content:
        fields["reasoning_content"] = reasoning_content
    return fields
