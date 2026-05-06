"""JSONL trace store."""

import json
import re
from pathlib import Path
from typing import Any, Protocol

from myagent.tracing.events import TraceEvent


class TraceStore(Protocol):
    """Small trace store contract used by AgentLoop."""

    def record(
        self,
        session_key: str,
        turn_id: str,
        event: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Append one trace event."""
        ...


class JsonlTraceStore:
    """Append trace events to one JSONL file per session."""

    def __init__(self, root: str | Path = "data/traces") -> None:
        self.root = Path(root)

    def record(
        self,
        session_key: str,
        turn_id: str,
        event: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Append one event to the session trace file."""
        self.root.mkdir(parents=True, exist_ok=True)
        trace_event = TraceEvent(
            session_key=session_key,
            turn_id=turn_id,
            event=event,
            data=data or {},
        )
        line = json.dumps(trace_event.to_dict(), ensure_ascii=False)
        with self.path_for_session(session_key).open("a", encoding="utf-8") as file:
            file.write(f"{line}\n")

    def path_for_session(self, session_key: str) -> Path:
        """Return the JSONL path for a session key."""
        return self.root / f"{safe_trace_name(session_key)}.jsonl"


def safe_trace_name(session_key: str) -> str:
    """Convert a session key into a readable safe filename stem."""
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", session_key).strip("._")
    return safe or "session"
