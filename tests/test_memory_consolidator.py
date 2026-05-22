from pathlib import Path
import shutil

from myagent.memory import MemoryConsolidator, MarkdownMemoryStore
from myagent.memory.markdown import MEMORY_HEADER, PROPOSALS_HEADER
from myagent.providers.base import ProviderResponse, ToolCall


class FakeProvider:
    """A test provider that returns a fixed consolidation response."""

    def __init__(
        self,
        response: str = "",
        *,
        always: list[str] | None = None,
        now: list[str] | None = None,
        use_tool: bool = True,
        arguments: object | None = None,
    ) -> None:
        self.response = response
        self.always = always or []
        self.now = now or []
        self.use_tool = use_tool
        self.arguments = arguments
        self.messages: list[list[dict]] = []
        self.tools: list[list[dict] | None] = []

    async def generate(self, messages: list[dict]) -> str:
        self.messages.append(messages)
        return self.response

    async def generate_response(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> ProviderResponse:
        self.messages.append(messages)
        self.tools.append(tools)
        if not self.use_tool:
            return ProviderResponse(content=self.response)
        arguments = self.arguments
        if arguments is None:
            arguments = {"always": self.always, "now": self.now}
        return ProviderResponse(
            tool_calls=[
                ToolCall(
                    id="save-memory-1",
                    name="save_memory",
                    arguments=arguments,
                )
            ]
        )


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
    store.propose_memory(
        content="User's name is Lin.",
        section_hint="Always",
        tags=["name"],
        importance=5,
    )

    provider = FakeProvider(always=["User's name is Lin."])
    consolidator = MemoryConsolidator(provider, store)

    result = await consolidator.consolidate()

    assert result is True
    memory = store.memory_path.read_text(encoding="utf-8")
    assert MEMORY_HEADER in memory
    assert "## Always" in memory
    assert "User's name is Lin." in memory


async def test_consolidator_archives_proposals() -> None:
    root = make_workspace("archive")
    store = MarkdownMemoryStore(root)
    store.ensure_layout()
    store.propose_memory(
        content="User prefers Python.",
        section_hint="Always",
        tags=["tech"],
        importance=3,
    )

    provider = FakeProvider(always=["User prefers Python."])
    consolidator = MemoryConsolidator(provider, store)

    await consolidator.consolidate()

    archive_dir = root / "archive" / "proposals"
    assert archive_dir.exists()
    archives = list(archive_dir.glob("MEMORY_PROPOSALS-*.md"))
    assert len(archives) == 1
    assert "User prefers Python." in archives[0].read_text(encoding="utf-8")


async def test_consolidator_clears_proposals_after_merge() -> None:
    root = make_workspace("clear")
    store = MarkdownMemoryStore(root)
    store.ensure_layout()
    store.propose_memory(
        content="User is preparing for interviews.",
        section_hint="Now",
        tags=["goal"],
        importance=4,
    )

    provider = FakeProvider(now=["User is preparing for interviews."])
    consolidator = MemoryConsolidator(provider, store)

    await consolidator.consolidate()

    proposals_text = store.proposals_path.read_text(encoding="utf-8").strip()
    assert proposals_text == PROPOSALS_HEADER


async def test_consolidator_returns_false_on_bad_llm_output() -> None:
    root = make_workspace("bad-llm")
    store = MarkdownMemoryStore(root)
    store.ensure_layout()
    store.propose_memory(
        content="User prefers Python.",
        section_hint="Always",
        tags=["tech"],
        importance=3,
    )

    provider = FakeProvider("I don't know what to do.", use_tool=False)
    consolidator = MemoryConsolidator(provider, store)

    result = await consolidator.consolidate()

    assert result is False
    proposals_text = store.proposals_path.read_text(encoding="utf-8")
    assert "User prefers Python." in proposals_text


async def test_consolidator_prompt_uses_budgets_instead_of_hard_counts() -> None:
    root = make_workspace("budget-prompt")
    store = MarkdownMemoryStore(root)
    store.ensure_layout()
    store.propose_memory(
        content="User prefers concise engineering explanations.",
        section_hint="Always",
        tags=["preference"],
        importance=4,
    )

    provider = FakeProvider(always=["User prefers concise engineering explanations."])
    consolidator = MemoryConsolidator(provider, store)

    await consolidator.consolidate()

    system_prompt = provider.messages[0][0]["content"]
    assert "Target budget: 4000 characters" in system_prompt
    assert "Target budget: 8000 characters" in system_prompt
    assert "Do not delete an item merely because it is old." in system_prompt
    assert "Maximum 10 bullets" not in system_prompt
    assert "Maximum 20 bullets" not in system_prompt


async def test_consolidator_returns_false_when_tool_payload_has_bad_markdown() -> None:
    root = make_workspace("bad-tool-markdown")
    store = MarkdownMemoryStore(root)
    store.ensure_layout()
    store.propose_memory(
        content="User prefers Python.",
        section_hint="Always",
        tags=["tech"],
        importance=3,
    )

    provider = FakeProvider(arguments={"always": "not a valid section", "now": 123})
    consolidator = MemoryConsolidator(provider, store)

    result = await consolidator.consolidate()

    assert result is False
    proposals_text = store.proposals_path.read_text(encoding="utf-8")
    assert "User prefers Python." in proposals_text


async def test_consolidator_renders_structured_sections_to_memory_markdown() -> None:
    root = make_workspace("normalize")
    store = MarkdownMemoryStore(root)
    store.ensure_layout()
    store.propose_memory(
        content="User prefers Python.",
        section_hint="Always",
        tags=["tech"],
        importance=3,
    )

    provider = FakeProvider(
        always=["- User prefers Python."],
        now=["* Current project is MyAgent."],
    )
    consolidator = MemoryConsolidator(provider, store)

    result = await consolidator.consolidate()

    assert result is True
    memory = store.memory_path.read_text(encoding="utf-8")
    assert memory == (
        "# Memory\n\n"
        "## Always\n\n"
        "- User prefers Python.\n\n"
        "## Now\n\n"
        "- Current project is MyAgent.\n"
    )
    assert "Extra" not in memory
