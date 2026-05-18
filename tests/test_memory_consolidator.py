from pathlib import Path
import shutil

from myagent.memory import MemoryConsolidator, MarkdownMemoryStore
from myagent.memory.markdown import MEMORY_HEADER, PROPOSALS_HEADER
from myagent.providers.base import ProviderResponse


class FakeProvider:
    """A test provider that returns a fixed response."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.messages: list[list[dict]] = []

    async def generate(self, messages: list[dict]) -> str:
        self.messages.append(messages)
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
        content="User's name is Lin.",
        section="Always",
        tags=["name"],
        importance=5,
    )

    new_memory = (
        "# Memory\n\n"
        "## Always\n\n"
        "- User's name is Lin.\n\n"
        "## Now\n\n"
        "## Later\n"
    )
    provider = FakeProvider(new_memory)
    consolidator = MemoryConsolidator(provider, store)

    result = await consolidator.consolidate()

    assert result is True
    memory_text = store.memory_path.read_text(encoding="utf-8")
    assert MEMORY_HEADER in memory_text
    assert "## Always" in memory_text
    assert "User's name is Lin." in memory_text


async def test_consolidator_archives_proposals() -> None:
    root = make_workspace("archive")
    store = MarkdownMemoryStore(root)
    store.ensure_layout()
    store.propose_long_term(
        content="User prefers Python.",
        section="Always",
        tags=["tech"],
        importance=3,
    )

    new_memory = (
        "# Memory\n\n"
        "## Always\n\n"
        "- User prefers Python.\n\n"
        "## Now\n\n"
        "## Later\n"
    )
    provider = FakeProvider(new_memory)
    consolidator = MemoryConsolidator(provider, store)

    await consolidator.consolidate()

    archive_dir = root / "memory" / "archive"
    assert archive_dir.exists()
    archives = list(archive_dir.glob("MEMORY_PROPOSALS-*.md"))
    assert len(archives) == 1
    assert "User prefers Python." in archives[0].read_text(encoding="utf-8")


async def test_consolidator_clears_proposals_after_merge() -> None:
    root = make_workspace("clear")
    store = MarkdownMemoryStore(root)
    store.ensure_layout()
    store.propose_long_term(
        content="User is preparing for interviews.",
        section="Now",
        tags=["goal"],
        importance=4,
    )

    new_memory = (
        "# Memory\n\n"
        "## Always\n\n"
        "## Now\n\n"
        "- User is preparing for interviews.\n\n"
        "## Later\n"
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
        content="User prefers Python.",
        section="Always",
        tags=["tech"],
        importance=3,
    )

    provider = FakeProvider("I don't know what to do.")
    consolidator = MemoryConsolidator(provider, store)

    result = await consolidator.consolidate()

    assert result is False
    proposals_text = store.proposals_path.read_text(encoding="utf-8")
    assert "User prefers Python." in proposals_text


async def test_consolidator_prompt_uses_budgets_instead_of_hard_counts() -> None:
    root = make_workspace("budget-prompt")
    store = MarkdownMemoryStore(root)
    store.ensure_layout()
    store.propose_long_term(
        content="User prefers concise engineering explanations.",
        section="Always",
        tags=["preference"],
        importance=4,
    )

    new_memory = (
        "# Memory\n\n"
        "## Always\n\n"
        "- User prefers concise engineering explanations.\n\n"
        "## Now\n\n"
        "## Later\n"
    )
    provider = FakeProvider(new_memory)
    consolidator = MemoryConsolidator(provider, store)

    await consolidator.consolidate()

    system_prompt = provider.messages[0][0]["content"]
    assert "Target budget: 4000 characters" in system_prompt
    assert "Target budget: 8000 characters" in system_prompt
    assert "Do not delete an item merely because it is old." in system_prompt
    assert "Maximum 10 bullets" not in system_prompt
    assert "Maximum 20 bullets" not in system_prompt
