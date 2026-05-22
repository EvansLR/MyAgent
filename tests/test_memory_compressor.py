from pathlib import Path
import shutil

from myagent.memory import MarkdownMemoryStore, VisibleMemoryCompressor
from myagent.providers.base import ProviderResponse, ToolCall


class ToolResponseProvider:
    def __init__(
        self,
        markdown: str = "",
        *,
        always: list[str] | None = None,
        now: list[str] | None = None,
        use_tool: bool = True,
        arguments: object | None = None,
    ) -> None:
        self.markdown = markdown
        self.always = always or []
        self.now = now or []
        self.use_tool = use_tool
        self.arguments = arguments
        self.messages: list[list[dict]] = []
        self.tools: list[list[dict] | None] = []

    async def generate(self, messages):
        return self.markdown

    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        self.messages.append(messages)
        self.tools.append(tools)
        if not self.use_tool:
            return ProviderResponse(content=self.markdown)
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
    root = Path(".test-workspaces") / "memory-compressor" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def write_large_memory(store: MarkdownMemoryStore) -> None:
    store.ensure_layout()
    store.memory_path.write_text(
        "# Memory\n\n## Always\n\n"
        + "- very large stable preference " * 20
        + "\n\n## Now\n\n"
        + "- very large project state " * 20
        + "\n",
        encoding="utf-8",
    )


async def test_visible_memory_compressor_uses_save_memory_tool() -> None:
    store = MarkdownMemoryStore(make_workspace("tool-call"))
    write_large_memory(store)
    provider = ToolResponseProvider(
        always=["Compact preference."],
        now=["Compact project state."],
    )
    compressor = VisibleMemoryCompressor(
        provider,
        store,
        token_limit=120,
        max_rounds=2,
        chars_per_token=1,
    )

    result = await compressor.compress_if_needed()

    memory = store.memory_path.read_text(encoding="utf-8")
    assert result.changed is True
    assert provider.tools[0][0]["function"]["name"] == "save_memory"
    assert "Compact preference." in memory
    assert "very large stable preference" not in memory


async def test_visible_memory_compressor_keeps_existing_file_on_bad_tool_output() -> None:
    store = MarkdownMemoryStore(make_workspace("bad-tool-output"))
    write_large_memory(store)
    original = store.memory_path.read_text(encoding="utf-8")
    provider = ToolResponseProvider(arguments={"always": ["ok"], "now": 123})
    compressor = VisibleMemoryCompressor(
        provider,
        store,
        token_limit=120,
        max_rounds=1,
        chars_per_token=1,
    )

    result = await compressor.compress_if_needed()

    assert result.changed is False
    assert store.memory_path.read_text(encoding="utf-8") == original


async def test_visible_memory_compressor_keeps_existing_file_without_tool_call() -> None:
    store = MarkdownMemoryStore(make_workspace("no-tool-call"))
    write_large_memory(store)
    original = store.memory_path.read_text(encoding="utf-8")
    provider = ToolResponseProvider(
        "# Memory\n\n## Always\n\n- Compact preference.\n\n## Now\n\n- Compact project state.",
        use_tool=False,
    )
    compressor = VisibleMemoryCompressor(
        provider,
        store,
        token_limit=120,
        max_rounds=1,
        chars_per_token=1,
    )

    result = await compressor.compress_if_needed()

    assert result.changed is False
    assert store.memory_path.read_text(encoding="utf-8") == original
