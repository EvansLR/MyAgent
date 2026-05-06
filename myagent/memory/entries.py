"""Memory entry data structures."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    """One saved long-term memory fact."""

    content: str
    session_key: str
    source: str = "user_explicit"
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex)
    ts: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "id": self.id,
            "ts": self.ts,
            "content": self.content,
            "source": self.source,
            "session_key": self.session_key,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEntry":
        """Build an entry from JSON data."""
        return cls(
            id=str(data["id"]),
            ts=str(data["ts"]),
            content=str(data["content"]),
            source=str(data.get("source", "user_explicit")),
            session_key=str(data.get("session_key", "")),
            metadata=dict(data.get("metadata", {})),
        )
