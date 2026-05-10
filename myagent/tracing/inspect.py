"""Read and summarize JSONL trace files."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from myagent.tracing.store import safe_trace_name


DEFAULT_TRACE_ROOT = Path("data/traces")


@dataclass(frozen=True, slots=True)
class TraceTurnSummary:
    """Compact summary for one traced turn."""

    turn_id: str
    event_count: int
    events: tuple[str, ...]
    stop_reason: str = ""
    iterations: int = 0
    tool_call_count: int = 0
    tool_error_count: int = 0
    warning_count: int = 0


def read_trace_events(
    session_key: str = "cli:default",
    trace_root: str | Path = DEFAULT_TRACE_ROOT,
) -> list[dict[str, Any]]:
    """Read all events for one session from a JSONL trace file."""
    path = trace_path_for_session(session_key, trace_root)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        events.append(json.loads(line))
    return events


def trace_path_for_session(
    session_key: str = "cli:default",
    trace_root: str | Path = DEFAULT_TRACE_ROOT,
) -> Path:
    """Return the JSONL path for a session."""
    return Path(trace_root) / f"{safe_trace_name(session_key)}.jsonl"


def summarize_turns(events: list[dict[str, Any]]) -> list[TraceTurnSummary]:
    """Summarize events grouped by turn_id in file order."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for event in events:
        turn_id = str(event.get("turn_id") or "")
        if not turn_id:
            continue
        if turn_id not in grouped:
            grouped[turn_id] = []
            order.append(turn_id)
        grouped[turn_id].append(event)

    return [_summarize_turn(turn_id, grouped[turn_id]) for turn_id in order]


def latest_turn_summary(events: list[dict[str, Any]]) -> TraceTurnSummary | None:
    """Return the latest turn summary, if any."""
    summaries = summarize_turns(events)
    if not summaries:
        return None
    return summaries[-1]


def format_turn_summary(summary: TraceTurnSummary) -> str:
    """Format a turn summary for CLI output."""
    lines = [
        f"turn_id: {summary.turn_id}",
        f"events: {summary.event_count}",
        f"event_names: {', '.join(summary.events)}",
    ]
    if summary.stop_reason:
        lines.extend(
            [
                f"stop_reason: {summary.stop_reason}",
                f"iterations: {summary.iterations}",
                f"tool_calls: {summary.tool_call_count}",
                f"tool_errors: {summary.tool_error_count}",
                f"warnings: {summary.warning_count}",
            ]
        )
    return "\n".join(lines)


def format_trace_events(events: list[dict[str, Any]], limit: int = 20) -> str:
    """Format recent trace events for CLI output."""
    recent = events[-max(limit, 0) :] if limit else []
    lines: list[str] = []
    for event in recent:
        data = event.get("data") or {}
        preview = _event_preview(str(event.get("event", "")), data)
        suffix = f" - {preview}" if preview else ""
        lines.append(f"{event.get('turn_id')} {event.get('event')}{suffix}")
    return "\n".join(lines)


def latest_context_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the latest context_built event, if any."""
    return next((event for event in reversed(events) if event.get("event") == "context_built"), None)


def format_context_summary(event: dict[str, Any]) -> str:
    """Format one context_built event as a compact CLI summary."""
    data = event.get("data") or {}
    context = data.get("context") or {}
    sections = context.get("sections") or []
    history = context.get("history") or {}
    warnings = context.get("warnings") or []
    lines = [
        f"turn_id: {event.get('turn_id')}",
        f"message_count: {context.get('message_count') or data.get('message_count') or 0}",
        f"estimated_tokens: {context.get('estimated_tokens') or 0}",
        f"total_chars: {context.get('total_chars') or 0}",
        (
            "history: "
            f"{history.get('included_messages') or 0}/{history.get('total_messages') or 0} included, "
            f"{history.get('dropped_messages') or 0} dropped"
        ),
    ]
    if warnings:
        lines.append(f"warnings: {', '.join(str(warning) for warning in warnings)}")
    lines.append("sections:")
    for section in sections:
        included = "yes" if section.get("included") else "no"
        lines.append(
            "- "
            f"{section.get('name')}: "
            f"tier={section.get('tier')}, "
            f"source={section.get('source')}, "
            f"tokens={section.get('estimated_tokens') or 0}, "
            f"chars={section.get('chars') or 0}, "
            f"included={included}"
        )
    return "\n".join(lines)


def _summarize_turn(turn_id: str, events: list[dict[str, Any]]) -> TraceTurnSummary:
    completed = next((event for event in reversed(events) if event.get("event") == "turn_completed"), None)
    data = completed.get("data", {}) if completed else {}
    return TraceTurnSummary(
        turn_id=turn_id,
        event_count=len(events),
        events=tuple(str(event.get("event")) for event in events),
        stop_reason=str(data.get("stop_reason") or ""),
        iterations=int(data.get("iterations") or 0),
        tool_call_count=int(data.get("tool_call_count") or 0),
        tool_error_count=int(data.get("tool_error_count") or 0),
        warning_count=int(data.get("warning_count") or 0),
    )


def _event_preview(event_name: str, data: dict[str, Any]) -> str:
    if event_name == "user_message":
        return _compact(str(data.get("content") or ""))
    if event_name == "llm_response":
        tools = data.get("tool_names") or []
        return f"tools={tools}"
    if event_name in {"tool_call", "tool_result"}:
        return str(data.get("tool_name") or "")
    if event_name == "skill_loaded":
        return _compact(
            f"{data.get('skill_id') or ''} "
            f"len={data.get('content_length') or 0}"
        )
    if event_name == "active_skill_set":
        return _compact(
            f"{data.get('skill_id') or ''} "
            f"scope={data.get('scope') or ''} "
            f"reason={data.get('reason') or ''}"
        )
    if event_name == "mcp_server_registered":
        return _compact(
            f"{data.get('server_name') or ''} "
            f"{data.get('transport') or ''} "
            f"tools={data.get('tool_count') or 0}/{data.get('discovered_tool_count') or 0}"
        )
    if event_name == "mcp_server_connect_failed":
        return _compact(f"{data.get('server_name') or ''} {data.get('error') or ''}")
    if event_name == "turn_completed":
        return str(data.get("stop_reason") or "")
    if event_name == "final_answer":
        return _compact(str(data.get("content_preview") or ""))
    return ""


def _compact(text: str, limit: int = 80) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."
