import json
from pathlib import Path
import shutil

from myagent.tracing import JsonlTraceStore


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
