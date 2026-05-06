import json
from pathlib import Path
import shutil

from myagent.memory import JsonlMemoryStore


def make_workspace(name: str) -> Path:
    root = Path(".test-workspaces") / "memory-store" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def test_jsonl_memory_store_adds_entries() -> None:
    path = make_workspace("add") / "facts.jsonl"
    store = JsonlMemoryStore(path)

    entry = store.add("我正在准备 Java 后端面试。", "cli:default")

    saved = json.loads(path.read_text(encoding="utf-8").strip())
    assert entry.content == "我正在准备 Java 后端面试。"
    assert saved["content"] == "我正在准备 Java 后端面试。"
    assert saved["source"] == "user_explicit"
    assert saved["session_key"] == "cli:default"


def test_jsonl_memory_store_lists_entries_in_file_order() -> None:
    path = make_workspace("list") / "facts.jsonl"
    store = JsonlMemoryStore(path)

    first = store.add("first", "cli:default")
    second = store.add("second", "cli:default")

    assert store.list_entries() == [first, second]
    assert store.list_entries(limit=1) == [second]
