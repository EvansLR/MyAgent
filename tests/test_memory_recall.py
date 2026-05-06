from pathlib import Path
import shutil

from myagent.memory import JsonlMemoryStore, MemoryRecall


def make_workspace(name: str) -> Path:
    root = Path(".test-workspaces") / "memory-recall" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def test_memory_recall_matches_keywords() -> None:
    store = JsonlMemoryStore(make_workspace("keywords") / "facts.jsonl")
    java = store.add("我正在准备 Java 后端面试。", "cli:default")
    store.add("我喜欢先写文档再写代码。", "cli:default")
    recall = MemoryRecall(store)

    results = recall.recall("Java 面试怎么准备？")

    assert results[0] == java


def test_memory_recall_falls_back_to_recent_entries() -> None:
    store = JsonlMemoryStore(make_workspace("recent") / "facts.jsonl")
    store.add("first", "cli:default")
    second = store.add("second", "cli:default")
    third = store.add("third", "cli:default")
    recall = MemoryRecall(store)

    results = recall.recall("unmatched query", limit=2)

    assert results == [third, second]
