"""Shared provider message helpers for tool-calling chat flows."""

from __future__ import annotations

import json

from myagent.agent.context.types import Message
from myagent.providers.base import ProviderResponse, ToolCall


def assistant_message(response: ProviderResponse) -> Message:
    """Build a plain assistant message for final provider responses."""
    message: Message = {
        "role": "assistant",
        "content": response.content,
    }
    message.update(response.extra_message_fields)
    return message


def assistant_tool_call_message(response: ProviderResponse) -> Message:
    """Build an assistant message containing tool calls for chat completions."""
    message: Message = {
        "role": "assistant",
        "content": response.content,
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.name,
                    "arguments": json.dumps(tool_call.arguments, ensure_ascii=False),
                },
            }
            for tool_call in response.tool_calls
        ],
    }
    message.update(response.extra_message_fields)
    return message


def tool_result_message(tool_call: ToolCall, result: str) -> Message:
    """Build a tool result message for chat completions."""
    return {
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": result,
    }
