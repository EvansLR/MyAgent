import json
from pathlib import Path
import shutil

from myagent.memory import JsonlMemoryStore, MarkdownMemoryStore


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


def test_markdown_memory_store_reads_core_memory() -> None:
    root = make_workspace("markdown-core")
    store = MarkdownMemoryStore(root)
    store.ensure_layout()
    store.memory_path.write_text(
        "# MyAgent Memory\n\n"
        "## Core Memory\n\n"
        "- 用户正在做个人助理 Agent。\n\n"
        "## Decisions\n\n"
        "- 暂时不做 QQ channel。\n",
        encoding="utf-8",
    )

    core_memory = store.read_core_memory()

    assert "用户正在做个人助理 Agent。" in core_memory
    assert "暂时不做 QQ channel。" not in core_memory


def test_markdown_memory_store_appends_and_searches_daily_memory() -> None:
    root = make_workspace("markdown-daily")
    store = MarkdownMemoryStore(root)

    record = store.append_daily("用户偏好先写文档再写代码。", tags=["workflow"], importance=3)
    results = store.search("文档 代码")

    assert record.id.startswith("daily-")
    assert results[0].id == record.id
    assert store.get(record.id).content == "用户偏好先写文档再写代码。"
