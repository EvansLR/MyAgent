"""Simple memory recall."""

import re

from myagent.memory.entries import MemoryEntry
from myagent.memory.store import JsonlMemoryStore


class MemoryRecall:
    """Recall memory entries using lightweight keyword overlap."""

    def __init__(self, store: JsonlMemoryStore, default_limit: int = 5) -> None:
        self.store = store
        self.default_limit = default_limit

    def recall(self, query: str, limit: int | None = None) -> list[MemoryEntry]:
        """Return matching memories, falling back to recent entries."""
        max_entries = limit or self.default_limit
        entries = self.store.list_entries()
        if not entries:
            return []

        query_terms = _terms(query)
        scored = [
            (len(query_terms & _terms(entry.content)), index, entry)
            for index, entry in enumerate(entries)
        ]
        matches = [
            (score, index, entry)
            for score, index, entry in scored
            if score > 0
        ]
        if not matches:
            return list(reversed(entries[-max_entries:]))

        matches.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [entry for _, _, entry in matches[:max_entries]]


def _terms(text: str) -> set[str]:
    """Extract coarse terms for English and CJK text."""
    normalized = text.lower()
    words = set(re.findall(r"[a-z0-9_]+", normalized))
    cjk_chars = set(re.findall(r"[\u4e00-\u9fff]", normalized))
    return words | cjk_chars
