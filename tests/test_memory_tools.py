from pathlib import Path
import shutil

from myagent.memory import MarkdownMemoryStore
from myagent.memory.consolidator import MemoryConsolidator
from myagent.providers.base import ProviderResponse, ToolCall
from myagent.tools.memory import (
    MemoryArchiveTool,
    MemoryConsolidateTool,
    MemoryForgetTool,
    MemoryGetTool,
    MemoryProposeTool,
    MemoryRememberTool,
    MemorySearchTool,
)


class ConsolidationProvider:
    def __init__(
        self,
        *,
        always: list[str] | None = None,
        now: list[str] | None = None,
    ) -> None:
        self.always = always or []
        self.now = now or []

    async def generate(self, messages: list[dict]) -> str:
        return ""

    async def generate_response(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> ProviderResponse:
        return ProviderResponse(
            tool_calls=[
                ToolCall(
                    id="save-memory-1",
                    name="save_memory",
                    arguments={"always": self.always, "now": self.now},
                )
            ]
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
        "# Memory\n\n## Always\n\n## Now\n"
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
    assert not (store.root / "archive" / "2026-05-18.md").exists()


async def test_memory_tools_archive_search_and_get() -> None:
    store = MarkdownMemoryStore(make_workspace("search"))

    archive_result = await MemoryArchiveTool(store).execute(
        note="User is preparing for a Java backend interview.",
        tags=["interview"],
        importance=4,
    )
    search_result = await MemorySearchTool(store).execute(query="Java interview")

    memory_id = archive_result.split(" ")[3]
    get_result = await MemoryGetTool(store).execute(memory_id=memory_id)

    assert "Archived memory note" in archive_result
    assert memory_id in search_result
    assert "User is preparing for a Java backend interview." in get_result


async def test_memory_remember_writes_visible_memory() -> None:
    store = MarkdownMemoryStore(make_workspace("remember"))

    result = await MemoryRememberTool(store).execute(
        content="User prefers documentation-first changes.",
        section="Always",
        tags=["preference"],
    )

    memory = (store.root / "MEMORY.md").read_text(encoding="utf-8")
    assert "Remembered" in result
    assert "User prefers documentation-first changes." in memory
    assert "User prefers documentation-first changes." in store.read_always_memory()
    assert store.read_now_memory() == ""


async def test_memory_archive_is_searchable_but_not_visible_by_default() -> None:
    store = MarkdownMemoryStore(make_workspace("archive"))

    await MemoryArchiveTool(store).execute(
        note="Old Feishu gateway notes are useful for interview examples.",
        tags=["project"],
        importance=3,
    )

    assert "Feishu gateway" not in store.read_always_memory()
    assert "Feishu gateway" not in store.read_now_memory()
    search_result = await MemorySearchTool(store).execute(query="Feishu gateway")
    assert "Feishu gateway" in search_result


async def test_memory_tool_can_create_proposal() -> None:
    store = MarkdownMemoryStore(make_workspace("proposal"))

    result = await MemoryProposeTool(store).execute(
        content="User may be preparing for a Java backend interview.",
        section_hint="Now",
        tags=["candidate"],
        importance=2,
    )

    proposals = (store.root / "MEMORY_PROPOSALS.md").read_text(encoding="utf-8")
    memory = (store.root / "MEMORY.md").read_text(encoding="utf-8")
    assert "Created memory proposal" in result
    assert "User may be preparing for a Java backend interview." in proposals
    assert "section_hint: Now" in proposals
    assert "User may be preparing for a Java backend interview." not in memory


async def test_memory_consolidate_tool_merges_pending_proposals() -> None:
    store = MarkdownMemoryStore(make_workspace("consolidate-tool"))
    store.propose_memory(
        content="User prefers short engineering explanations.",
        section_hint="Always",
        tags=["preference"],
        importance=4,
    )
    provider = ConsolidationProvider(
        always=["User prefers short engineering explanations."]
    )
    tool = MemoryConsolidateTool(MemoryConsolidator(provider, store))

    result = await tool.execute()

    assert "Consolidated pending memory proposals" in result
    assert "short engineering explanations" in store.memory_path.read_text(
        encoding="utf-8"
    )
    assert store.proposals_path.read_text(encoding="utf-8").strip() == "# Memory Proposals"


async def test_memory_consolidate_tool_reports_no_pending_proposals() -> None:
    store = MarkdownMemoryStore(make_workspace("consolidate-empty"))
    tool = MemoryConsolidateTool(
        MemoryConsolidator(ConsolidationProvider(), store)
    )

    result = await tool.execute()

    assert result == "No pending memory proposals to consolidate."


async def test_memory_tool_forgets_matching_memory() -> None:
    store = MarkdownMemoryStore(make_workspace("forget"))
    await MemoryRememberTool(store).execute(
        content="User is preparing for a Java backend interview.",
        section="Now",
        tags=["interview"],
    )
    await MemoryArchiveTool(store).execute(
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
