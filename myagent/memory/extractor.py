"""Memory extraction for history chunks that are about to be compacted."""

from __future__ import annotations

import json
from typing import Any

from myagent.memory.markdown import MarkdownMemoryStore
from myagent.providers.base import BaseProvider


SAVE_EXTRACTED_MEMORY_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_extracted_memory",
            "description": "Return candidate memories extracted from a conversation chunk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {
                                    "type": "string",
                                    "description": "Short standalone memory candidate.",
                                },
                                "target": {
                                    "type": "string",
                                    "enum": ["archive", "long_term"],
                                    "description": "archive for episodic notes, long_term for durable memory proposals.",
                                },
                                "section": {
                                    "type": "string",
                                    "enum": ["Always", "Now"],
                                    "description": "Visible memory section when target is long_term.",
                                },
                                "importance": {
                                    "type": "integer",
                                    "description": "Importance from 1 to 5.",
                                },
                                "tags": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": ["content", "target"],
                        },
                    },
                },
                "required": ["items"],
            },
        },
    }
]


class MemoryExtractor:
    """Ask the model to extract candidate memory from a history chunk."""

    def __init__(self, provider: BaseProvider, store: MarkdownMemoryStore) -> None:
        self.provider = provider
        self.store = store

    async def extract_messages(
        self,
        messages: list[dict[str, object]],
        *,
        source: str = "pre_context_compaction",
    ) -> list[str]:
        """Extract candidate memories and write them to proposals or archive."""
        response = await self.provider.generate_response(
            [
                {"role": "system", "content": _EXTRACTOR_SYSTEM_PROMPT},
                {"role": "user", "content": _build_messages_prompt(messages)},
            ],
            tools=SAVE_EXTRACTED_MEMORY_TOOL,
        )
        items = memory_items_from_tool_calls(response.tool_calls)
        written_ids: list[str] = []
        for item in items:
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            tags = _as_str_list(item.get("tags"))
            importance = _as_int(item.get("importance"), default=1)
            target = str(item.get("target", "archive")).strip().lower()
            if target == "long_term":
                section_hint = str(item.get("section", "Now")).strip() or "Now"
                record = self.store.propose_memory(
                    content=content,
                    section_hint=section_hint,
                    tags=tags,
                    importance=importance,
                    source=source,
                )
            else:
                record = self.store.append_archive(
                    note=content,
                    tags=tags,
                    importance=importance,
                    source=source,
                )
            written_ids.append(record.id)
        return written_ids


_EXTRACTOR_SYSTEM_PROMPT = """You are MyAgent's memory extractor.
Extract only information that is likely to help MyAgent serve the user in future turns.
Call save_extracted_memory with extracted memory candidates.
If there is nothing worth remembering, call save_extracted_memory with {"items":[]}.

Be conservative. Do not record:
- short acknowledgements, approvals, or conversational filler
- one-off tool usage, command output, or file-reading steps
- implementation details that matter only inside the completed turn
- assistant plans unless they describe an unfinished user-relevant open loop
- raw conversation text unless it is itself a durable memory

Use target=archive for episodic notes, completed work, temporary project state, or uncertain observations.
Use target=long_term only for stable user preferences, long-term goals, identity/background, durable project facts, or decisions that should affect future behavior.

For long_term memories, use one of these sections:
- Always: stable, high-signal information that should be visible in every conversation
- Now: current project stage, active open loops, and recent decisions"""


def _build_messages_prompt(messages: list[dict[str, object]]) -> str:
    lines = ["## History Chunk To Inspect"]
    for message in messages:
        role = str(message.get("role", "unknown")).upper()
        content = message.get("content", "")
        if not isinstance(content, str):
            content = repr(content)
        lines.append(f"[{role}] {content}")
    return "\n".join(lines)


def memory_items_from_tool_calls(tool_calls: list[Any]) -> list[dict[str, Any]]:
    """Extract memory candidate items from a save_extracted_memory tool call."""
    for call in tool_calls:
        if getattr(call, "name", "") != "save_extracted_memory":
            continue
        arguments = _normalize_arguments(getattr(call, "arguments", {}))
        if arguments is None:
            continue
        return _normalize_items(arguments.get("items", []))
    return []


def _normalize_arguments(arguments: object) -> dict[str, object] | None:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return None
    return arguments if isinstance(arguments, dict) else None


def _normalize_items(items: object) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _as_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default
