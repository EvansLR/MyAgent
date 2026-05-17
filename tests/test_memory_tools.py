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


def test_memory_store_migrates_legacy_dreams_file_to_proposals() -> None:
    root = make_workspace("legacy-dreams")
    (root / "DREAMS.md").write_text(
        "# Memory Dreams\n\n"
        "## proposal-legacy\n\n"
        "- target_section: Facts\n\n"
        "Legacy proposal text.\n",
        encoding="utf-8",
    )

    MarkdownMemoryStore(root).ensure_layout()

    proposals = (root / "MEMORY_PROPOSALS.md").read_text(encoding="utf-8")
    assert "# Memory Proposals" in proposals
    assert "Legacy proposal text." in proposals


async def test_memory_tools_append_search_and_get() -> None:
    store = MarkdownMemoryStore(make_workspace("search"))

    append_result = await MemoryAppendDailyTool(store).execute(
        note="用户正在准备 Java 后端面试。",
        tags=["interview"],
        importance=4,
    )
    search_result = await MemorySearchTool(store).execute(query="Java 面试")

    memory_id = append_result.split(" ")[3]
    get_result = await MemoryGetTool(store).execute(memory_id=memory_id)

    assert "Saved daily memory" in append_result
    assert memory_id in search_result
    assert "用户正在准备 Java 后端面试。" in get_result


async def test_memory_tool_saves_explicit_long_term_memory() -> None:
    store = MarkdownMemoryStore(make_workspace("proposal"))

    result = await MemoryProposeLongTermTool(store).execute(
        content="用户偏好文档优先。",
        section="Profile",
        tags=["preference"],
        importance=4,
        apply=True,
    )

    memory = (store.root / "MEMORY.md").read_text(encoding="utf-8")
    assert "Saved long-term memory" in result
    assert "用户偏好文档优先。" in memory
    assert "## Profile" in store.read_core_memory()


async def test_memory_tool_can_create_unapplied_long_term_proposal() -> None:
    store = MarkdownMemoryStore(make_workspace("unapplied-proposal"))

    result = await MemoryProposeLongTermTool(store).execute(
        content="用户可能在准备 Java 后端面试。",
        section="Facts",
        tags=["candidate"],
        importance=2,
        apply=False,
    )

    proposals = (store.root / "MEMORY_PROPOSALS.md").read_text(encoding="utf-8")
    memory = (store.root / "MEMORY.md").read_text(encoding="utf-8")
    assert "Created long-term memory proposal" in result
    assert "用户可能在准备 Java 后端面试。" in proposals
    assert "用户可能在准备 Java 后端面试。" not in memory


async def test_memory_tool_defaults_to_long_term_proposal() -> None:
    store = MarkdownMemoryStore(make_workspace("default-proposal"))

    result = await MemoryProposeLongTermTool(store).execute(
        content="User prefers small incremental implementation.",
        section="Preferences",
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
        content="用户正在准备 Java 后端面试。",
        section="Active Goals",
        tags=["interview"],
        importance=4,
        apply=True,
    )
    await MemoryAppendDailyTool(store).execute(
        note="用户正在准备 Java 后端面试。",
        tags=["interview"],
        importance=2,
    )

    result = await MemoryForgetTool(store).execute(query="Java 后端面试")

    assert "Forgot 2 markdown memory item" in result
    assert "Java 后端面试" not in (store.root / "MEMORY.md").read_text(encoding="utf-8")
    assert store.search("Java 后端面试") == []
