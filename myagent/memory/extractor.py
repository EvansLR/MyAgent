"""Post-turn memory extraction."""

from __future__ import annotations

import json
from typing import Any

from myagent.memory.markdown import MarkdownMemoryStore
from myagent.providers.base import BaseProvider, Message


class MemoryExtractor:
    """Ask the model to extract candidate memory after a completed turn."""

    def __init__(self, provider: BaseProvider, store: MarkdownMemoryStore) -> None:
        self.provider = provider
        self.store = store

    async def extract_turn(self, user_message: str, assistant_answer: str) -> list[str]:
        """Extract candidate memories and write them to daily notes or proposals."""
        response = await self.provider.generate(
            [
                {"role": "system", "content": _EXTRACTOR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "User message:\n"
                        f"{user_message.strip()}\n\n"
                        "Assistant answer:\n"
                        f"{assistant_answer.strip()}"
                    ),
                },
            ]
        )
        items = _parse_items(response)
        written_ids: list[str] = []
        for item in items:
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            tags = _as_str_list(item.get("tags"))
            importance = _as_int(item.get("importance"), default=1)
            target = str(item.get("target", "daily")).strip().lower()
            if target == "long_term":
                section = str(item.get("section", "Later")).strip() or "Later"
                record = self.store.propose_long_term(
                    content=content,
                    section=section,
                    tags=tags,
                    importance=importance,
                    source="post_turn_extractor",
                    apply=False,
                )
            else:
                record = self.store.append_daily(
                    note=content,
                    tags=tags,
                    importance=importance,
                    source="post_turn_extractor",
                )
            written_ids.append(record.id)
        return written_ids


_EXTRACTOR_SYSTEM_PROMPT = """You are MyAgent's memory extractor.
Extract only information that is likely to help MyAgent serve the user in future turns.
Return strict JSON only:
{"items":[{"content":"short standalone memory","target":"daily|long_term","section":"Later","importance":1,"tags":["tag"]}]}
If there is nothing worth remembering, return {"items":[]}.

Be conservative. Do not record:
- short acknowledgements, approvals, or conversational filler
- one-off tool usage, command output, or file-reading steps
- implementation details that matter only inside the completed turn
- assistant plans unless they describe an unfinished user-relevant open loop
- raw conversation text unless it is itself a durable memory

Use target=daily for recent working context, open loops, temporary project state, or uncertain observations.
Use target=long_term only for stable user preferences, long-term goals, identity/background, durable project facts, or decisions that should affect future behavior.

For long_term memories, use one of these sections:
- Always: stable, high-signal information that should be visible in every conversation
- Now: current project stage, active open loops, and recent decisions
- Later: useful but non-urgent facts, historical context, references, and lower-confidence notes"""


def _parse_items(response: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        return []
    items = data.get("items", [])
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
