from pathlib import Path
import shutil

from myagent.memory import MarkdownMemoryStore
from myagent.tools.memory import (
    MemoryAppendDailyTool,
    MemoryForgetTool,
    MemoryGetTool,
    MemoryProposeLongTermTool,
    MemorySearchTool,
)


def make_workspace(name: str) -> Path:
    root = Path(".test-workspaces") / "memory-tools" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def test_memory_store_creates_proposals_file() -> None:
    root = make_workspace("proposals")

    MarkdownMemoryStore(root).ensure_layout()

    proposals = (root / "MEMORY_PROPOSALS.md").read_text(encoding="utf-8")
    assert proposals == "# Memory Proposals\n\n"


def test_default_memory_store_uses_dedicated_memory_directory(monkeypatch) -> None:
    home = make_workspace("home-default")
    monkeypatch.setattr(Path, "home", lambda: home)

    store = MarkdownMemoryStore()
    store.ensure_layout()

    assert store.root == home / ".myagent" / "memory"
    assert (store.root / "MEMORY.md").exists()
    assert (store.root / "MEMORY.md").read_text(encoding="utf-8") == (
        "# Memory\n\n## Always\n\n## Now\n\n## Later\n"
    )


def test_default_memory_store_does_not_read_legacy_workspace_memory(monkeypatch) -> None:
    home = make_workspace("home-no-migrate")
    legacy = home / ".myagent" / "workspace"
    legacy.mkdir(parents=True)
    (legacy / "MEMORY.md").write_text(
        "# Long-term Memory\n\n## Profile\n\n- Legacy profile.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(Path, "home", lambda: home)

    store = MarkdownMemoryStore()
    store.ensure_layout()

    assert "Legacy profile" not in (store.root / "MEMORY.md").read_text(encoding="utf-8")
    assert not (store.root / "daily" / "2026-05-18.md").exists()


async def test_memory_tools_append_search_and_get() -> None:
    store = MarkdownMemoryStore(make_workspace("search"))

    append_result = await MemoryAppendDailyTool(store).execute(
        note="User is preparing for a Java backend interview.",
        tags=["interview"],
        importance=4,
    )
    search_result = await MemorySearchTool(store).execute(query="Java interview")

    memory_id = append_result.split(" ")[3]
    get_result = await MemoryGetTool(store).execute(memory_id=memory_id)

    assert "Saved daily memory" in append_result
    assert memory_id in search_result
    assert "User is preparing for a Java backend interview." in get_result


async def test_memory_tool_saves_explicit_long_term_memory() -> None:
    store = MarkdownMemoryStore(make_workspace("proposal"))

    result = await MemoryProposeLongTermTool(store).execute(
        content="User prefers documentation-first changes.",
        section="Always",
        tags=["preference"],
        importance=4,
        apply=True,
    )

    memory = (store.root / "MEMORY.md").read_text(encoding="utf-8")
    assert "Saved long-term memory" in result
    assert "User prefers documentation-first changes." in memory
    assert "## Always" in store.read_core_memory()
    assert "User prefers documentation-first changes." in store.read_always_memory()
    assert store.read_now_memory() == ""


async def test_memory_later_is_searchable_but_not_visible_by_default() -> None:
    store = MarkdownMemoryStore(make_workspace("later"))

    await MemoryProposeLongTermTool(store).execute(
        content="Old Feishu gateway notes are useful for interview examples.",
        section="Later",
        tags=["project"],
        importance=3,
        apply=True,
    )

    assert "Feishu gateway" not in store.read_core_memory()
    search_result = await MemorySearchTool(store).execute(query="Feishu gateway")
    assert "Feishu gateway" in search_result


async def test_memory_tool_can_create_unapplied_long_term_proposal() -> None:
    store = MarkdownMemoryStore(make_workspace("unapplied-proposal"))

    result = await MemoryProposeLongTermTool(store).execute(
        content="User may be preparing for a Java backend interview.",
        section="Later",
        tags=["candidate"],
        importance=2,
        apply=False,
    )

    proposals = (store.root / "MEMORY_PROPOSALS.md").read_text(encoding="utf-8")
    memory = (store.root / "MEMORY.md").read_text(encoding="utf-8")
    assert "Created long-term memory proposal" in result
    assert "User may be preparing for a Java backend interview." in proposals
    assert "User may be preparing for a Java backend interview." not in memory


async def test_memory_tool_defaults_to_long_term_proposal() -> None:
    store = MarkdownMemoryStore(make_workspace("default-proposal"))

    result = await MemoryProposeLongTermTool(store).execute(
        content="User prefers small incremental implementation.",
        section="Always",
        tags=["workflow"],
        importance=3,
    )

    proposals = (store.root / "MEMORY_PROPOSALS.md").read_text(encoding="utf-8")
    memory = (store.root / "MEMORY.md").read_text(encoding="utf-8")
    assert "Created long-term memory proposal" in result
    assert "User prefers small incremental implementation." in proposals
    assert "User prefers small incremental implementation." not in memory


async def test_memory_tool_forgets_matching_memory() -> None:
    store = MarkdownMemoryStore(make_workspace("forget"))
    await MemoryProposeLongTermTool(store).execute(
        content="User is preparing for a Java backend interview.",
        section="Now",
        tags=["interview"],
        importance=4,
        apply=True,
    )
    await MemoryAppendDailyTool(store).execute(
        note="User is preparing for a Java backend interview.",
        tags=["interview"],
        importance=2,
    )

    result = await MemoryForgetTool(store).execute(query="Java backend interview")

    assert "Forgot 2 markdown memory item" in result
    assert "Java backend interview" not in (store.root / "MEMORY.md").read_text(
        encoding="utf-8"
    )
    assert store.search("Java backend interview") == []
