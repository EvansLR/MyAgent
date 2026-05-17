import json
from pathlib import Path
import shutil

from myagent.tracing import JsonlTraceStore
from myagent.tracing.html_report import (
    build_trace_report_html,
    build_trace_viewer_html,
    write_trace_report,
    write_trace_viewer,
)
from myagent.tracing.inspect import (
    format_context_summary,
    format_trace_events,
    format_turn_summary,
    latest_context_event,
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


def test_trace_inspect_formats_runtime_events() -> None:
    events = [
        {
            "turn_id": "skills",
            "event": "skill_loaded",
            "data": {"skill_id": "frontend-design", "content_length": 123},
        },
        {
            "turn_id": "skills",
            "event": "active_skill_set",
            "data": {
                "skill_id": "frontend-design",
                "scope": "turn",
                "reason": "loaded_by_skill_get",
            },
        },
        {
            "turn_id": "startup",
            "event": "mcp_server_registered",
            "data": {
                "server_name": "didi-mcp",
                "transport": "http",
                "tool_count": 13,
                "discovered_tool_count": 13,
            },
        },
    ]

    formatted = format_trace_events(events, limit=3)

    assert "skills skill_loaded - frontend-design len=123" in formatted
    assert "skills active_skill_set - frontend-design scope=turn reason=loaded_by_skill_get" in formatted
    assert "startup mcp_server_registered - didi-mcp http tools=13/13" in formatted


def test_trace_inspect_formats_latest_context_summary() -> None:
    events = [
        {
            "turn_id": "turn-1",
            "event": "context_built",
            "data": {
                "message_count": 3,
                "context": {
                    "total_chars": 1200,
                    "estimated_tokens": 300,
                    "estimated_tokens_before_budget": 600,
                    "max_prompt_tokens": 500,
                    "message_count": 3,
                    "sections": [
                        {
                            "name": "Identity",
                            "kind": "instruction",
                            "tier": "protected",
                            "source": "identity",
                            "chars": 100,
                            "estimated_tokens": 25,
                            "included": True,
                            "reason": "included",
                        },
                        {
                            "name": "Available Skills",
                            "kind": "skill_summary",
                            "tier": "medium",
                            "source": "skills:summary",
                            "chars": 800,
                            "estimated_tokens": 200,
                            "included": False,
                            "reason": "budget_exceeded",
                        },
                    ],
                    "history": {
                        "total_messages": 4,
                        "included_messages": 2,
                        "dropped_messages": 2,
                        "reserved_tokens": 175,
                        "estimated_tokens": 80,
                    },
                    "warnings": ["history_trimmed"],
                },
            },
        }
    ]

    event = latest_context_event(events)
    assert event is not None
    formatted = format_context_summary(event)

    assert "turn_id: turn-1" in formatted
    assert "estimated_tokens: 300" in formatted
    assert "estimated_tokens_before_budget: 600" in formatted
    assert "max_prompt_tokens: 500" in formatted
    assert "history: 2/4 included, 2 dropped, reserved=175, tokens=80" in formatted
    assert "warnings: history_trimmed" in formatted
    assert "- Identity: kind=instruction, tier=protected, source=identity, tokens=25, chars=100, included=yes" in formatted
    assert "- Available Skills: kind=skill_summary, tier=medium, source=skills:summary, tokens=200, chars=800, included=no, reason=budget_exceeded" in formatted


def test_trace_inspect_formats_context_dropped_event() -> None:
    events = [
        {
            "turn_id": "turn-1",
            "event": "context_dropped",
            "data": {
                "dropped_sections": [{"name": "Available Skills"}],
                "dropped_history_by_token_budget": 2,
                "estimated_tokens_before": 900,
                "estimated_tokens_after": 500,
            },
        }
    ]

    formatted = format_trace_events(events, limit=1)

    assert "turn-1 context_dropped - sections=1 history=2 tokens=900->500" in formatted


def test_trace_html_report_includes_context_and_runtime_sections() -> None:
    events = [
        {
            "turn_id": "turn-1",
            "event": "context_built",
            "data": {
                "context": {
                    "total_chars": 1200,
                    "estimated_tokens": 300,
                    "message_count": 3,
                    "sections": [
                        {
                            "name": "Identity",
                            "tier": "protected",
                            "source": "identity",
                            "chars": 100,
                            "estimated_tokens": 25,
                            "included": True,
                        }
                    ],
                    "history": {
                        "total_messages": 0,
                        "included_messages": 0,
                        "dropped_messages": 0,
                    },
                },
            },
        },
        {
            "turn_id": "turn-1",
            "event": "turn_completed",
            "data": {"stop_reason": "final_output", "tool_call_count": 1, "warning_count": 0},
        },
    ]
    skills = [
        {
            "turn_id": "skills",
            "event": "active_skill_set",
            "data": {"skill_id": "frontend-design", "scope": "turn"},
        }
    ]
    startup = [
        {
            "turn_id": "startup",
            "event": "mcp_server_registered",
            "data": {"server_name": "didi-mcp", "transport": "http", "tool_count": 13},
        }
    ]

    html = build_trace_report_html(events, skills, startup)

    assert "MyAgent Trace Report" in html
    assert "Context Assembly" in html
    assert "Identity" in html
    assert "frontend-design" in html
    assert "didi-mcp" in html


def test_write_trace_report_writes_static_html_file() -> None:
    root = make_workspace("html-report")
    store = JsonlTraceStore(root / "traces")
    store.record(
        "cli:default",
        "turn-1",
        "context_built",
        {
            "context": {
                "total_chars": 1200,
                "estimated_tokens": 300,
                "message_count": 3,
                "sections": [],
                "history": {
                    "total_messages": 0,
                    "included_messages": 0,
                    "dropped_messages": 0,
                },
            }
        },
    )
    output = root / "trace-report.html"

    written = write_trace_report(output, root / "traces")

    assert written == output
    assert output.exists()
    assert "MyAgent Trace Report" in output.read_text(encoding="utf-8")


def test_trace_viewer_html_supports_file_loading() -> None:
    html = build_trace_viewer_html()

    assert "MyAgent Trace Viewer" in html
    assert 'input id="files" type="file" multiple' in html
    assert "context_built" in html
    assert "active_skill_set" in html


def test_write_trace_viewer_writes_static_viewer_file() -> None:
    root = make_workspace("html-viewer")
    output = root / "viewer.html"

    written = write_trace_viewer(output)

    assert written == output
    assert output.exists()
    assert "MyAgent Trace Viewer" in output.read_text(encoding="utf-8")
