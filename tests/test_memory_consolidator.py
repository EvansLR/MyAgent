from pathlib import Path
import shutil

import pytest

from myagent.memory import MemoryConsolidator, MarkdownMemoryStore
from myagent.memory.markdown import PROPOSALS_HEADER
from myagent.providers.base import ProviderResponse


class FakeProvider:
    """A test provider that returns a fixed response."""

    def __init__(self, response: str) -> None:
        self.response = response

    async def generate(self, messages: list[dict]) -> str:
        return self.response

    async def generate_response(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> ProviderResponse:
        return ProviderResponse(content=self.response)


def make_workspace(name: str) -> Path:
    root = Path(".test-workspaces") / "consolidator" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


async def test_consolidator_noop_when_proposals_empty() -> None:
    root = make_workspace("empty-proposals")
    store = MarkdownMemoryStore(root)
    store.ensure_layout()
    provider = FakeProvider("")
    consolidator = MemoryConsolidator(provider, store)

    result = await consolidator.consolidate()

    assert result is False


async def test_consolidator_noop_when_proposals_has_only_header() -> None:
    root = make_workspace("header-only")
    store = MarkdownMemoryStore(root)
    store.ensure_layout()
    store.proposals_path.write_text(f"{PROPOSALS_HEADER}\n\n", encoding="utf-8")
    provider = FakeProvider("")
    consolidator = MemoryConsolidator(provider, store)

    result = await consolidator.consolidate()

    assert result is False


async def test_consolidator_merges_proposals_into_memory() -> None:
    root = make_workspace("merge")
    store = MarkdownMemoryStore(root)
    store.ensure_layout()
    store.propose_long_term(
        content="用户的名字是 Lin。",
        section="Profile",
        tags=["name"],
        importance=5,
    )

    new_memory = (
        "# 长期记忆\n\n"
        "## Profile\n\n"
        "- 用户的名字是 Lin。\n\n"
        "## Active Goals\n\n"
        "## Preferences\n\n"
        "## Facts\n\n"
        "## Notes\n"
    )
    provider = FakeProvider(new_memory)
    consolidator = MemoryConsolidator(provider, store)

    result = await consolidator.consolidate()

    assert result is True
    memory_text = store.memory_path.read_text(encoding="utf-8")
    assert "# 长期记忆" in memory_text
    assert "## Profile" in memory_text
    assert "用户的名字是 Lin。" in memory_text


async def test_consolidator_archives_proposals() -> None:
    root = make_workspace("archive")
    store = MarkdownMemoryStore(root)
    store.ensure_layout()
    store.propose_long_term(
        content="用户偏好 Python。",
        section="Preferences",
        tags=["tech"],
        importance=3,
    )

    new_memory = (
        "# 长期记忆\n\n"
        "## Profile\n\n"
        "## Active Goals\n\n"
        "## Preferences\n\n"
        "- 用户偏好 Python。\n\n"
        "## Facts\n\n"
        "## Notes\n"
    )
    provider = FakeProvider(new_memory)
    consolidator = MemoryConsolidator(provider, store)

    await consolidator.consolidate()

    archive_dir = root / "memory" / "archive"
    assert archive_dir.exists()
    archives = list(archive_dir.glob("MEMORY_PROPOSALS-*.md"))
    assert len(archives) == 1
    assert "用户偏好 Python。" in archives[0].read_text(encoding="utf-8")


async def test_consolidator_clears_proposals_after_merge() -> None:
    root = make_workspace("clear")
    store = MarkdownMemoryStore(root)
    store.ensure_layout()
    store.propose_long_term(
        content="用户正在准备面试。",
        section="Active Goals",
        tags=["goal"],
        importance=4,
    )

    new_memory = (
        "# 长期记忆\n\n"
        "## Profile\n\n"
        "## Active Goals\n\n"
        "- 用户正在准备面试。\n\n"
        "## Preferences\n\n"
        "## Facts\n\n"
        "## Notes\n"
    )
    provider = FakeProvider(new_memory)
    consolidator = MemoryConsolidator(provider, store)

    await consolidator.consolidate()

    proposals_text = store.proposals_path.read_text(encoding="utf-8").strip()
    assert proposals_text == PROPOSALS_HEADER


async def test_consolidator_returns_false_on_bad_llm_output() -> None:
    root = make_workspace("bad-llm")
    store = MarkdownMemoryStore(root)
    store.ensure_layout()
    store.propose_long_term(
        content="用户偏好 Python。",
        section="Preferences",
        tags=["tech"],
        importance=3,
    )

    provider = FakeProvider("I don't know what to do.")
    consolidator = MemoryConsolidator(provider, store)

    result = await consolidator.consolidate()

    assert result is False
    # Proposals should remain intact on failure
    proposals_text = store.proposals_path.read_text(encoding="utf-8")
    assert "用户偏好 Python。" in proposals_text
