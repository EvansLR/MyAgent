import json
from pathlib import Path
import shutil

from myagent.tracing import JsonlTraceStore
from myagent.tracing.inspect import (
    format_trace_events,
    format_turn_summary,
    latest_turn_summary,
    read_trace_events,
    summarize_turns,
)


def make_workspace(name: str) -> Path:
    root = Path(".test-workspaces") / "trace-store" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def read_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_jsonl_trace_store_appends_events() -> None:
    root = make_workspace("append")
    store = JsonlTraceStore(root)

    store.record("cli:default", "turn-1", "user_message", {"content": "hello"})
    store.record("cli:default", "turn-1", "final_answer", {"content_preview": "hi"})

    events = read_events(root / "cli_default.jsonl")

    assert [event["event"] for event in events] == ["user_message", "final_answer"]
    assert events[0]["session_key"] == "cli:default"
    assert events[0]["turn_id"] == "turn-1"
    assert events[0]["data"] == {"content": "hello"}


def test_jsonl_trace_store_uses_safe_session_filename() -> None:
    root = make_workspace("safe-name")
    store = JsonlTraceStore(root)

    store.record("cli:session/with spaces", "turn-1", "user_message")

    assert store.path_for_session("cli:session/with spaces").name == "cli_session_with_spaces.jsonl"
    assert (root / "cli_session_with_spaces.jsonl").exists()


def test_trace_inspect_summarizes_latest_turn() -> None:
    root = make_workspace("inspect-latest")
    store = JsonlTraceStore(root)
    store.record("cli:default", "turn-1", "user_message", {"content": "hello"})
    store.record(
        "cli:default",
        "turn-1",
        "turn_completed",
        {
            "stop_reason": "final_output",
            "iterations": 2,
            "tool_call_count": 1,
            "tool_error_count": 0,
            "warning_count": 0,
        },
    )

    events = read_trace_events("cli:default", root)
    summary = latest_turn_summary(events)

    assert summary is not None
    assert summary.turn_id == "turn-1"
    assert summary.stop_reason == "final_output"
    assert summary.iterations == 2
    assert summary.tool_call_count == 1
    assert "stop_reason: final_output" in format_turn_summary(summary)


def test_trace_inspect_formats_recent_events() -> None:
    events = [
        {
            "turn_id": "turn-1",
            "event": "user_message",
            "data": {"content": "hello"},
        },
        {
            "turn_id": "turn-1",
            "event": "turn_completed",
            "data": {"stop_reason": "final_output"},
        },
    ]

    summaries = summarize_turns(events)
    formatted = format_trace_events(events, limit=2)

    assert len(summaries) == 1
    assert summaries[0].events == ("user_message", "turn_completed")
    assert "turn-1 user_message - hello" in formatted
    assert "turn-1 turn_completed - final_output" in formatted
