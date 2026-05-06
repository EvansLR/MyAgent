"""Trace event data structures."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """One append-only event in an agent trace."""

    session_key: str
    turn_id: str
    event: str
    data: dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "ts": self.ts,
            "session_key": self.session_key,
            "turn_id": self.turn_id,
            "event": self.event,
            "data": self.data,
        }
