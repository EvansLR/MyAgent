"""JSONL memory store."""

import json
from pathlib import Path
from typing import Any

from myagent.memory.entries import MemoryEntry


class JsonlMemoryStore:
    """Append-only memory store backed by a JSONL file."""

    def __init__(self, path: str | Path = "data/memory/facts.jsonl") -> None:
        self.path = Path(path)

    def add(
        self,
        content: str,
        session_key: str,
        *,
        source: str = "user_explicit",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        """Append a memory entry and return it."""
        entry = MemoryEntry(
            content=content.strip(),
            session_key=session_key,
            source=source,
            metadata=metadata or {},
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(f"{json.dumps(entry.to_dict(), ensure_ascii=False)}\n")
        return entry

    def list_entries(self, limit: int | None = None) -> list[MemoryEntry]:
        """Read memory entries in file order."""
        if not self.path.exists():
            return []
        entries = [
            MemoryEntry.from_dict(json.loads(line))
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if limit is None:
            return entries
        return entries[-limit:]
