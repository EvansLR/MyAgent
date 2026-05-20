import json
from pathlib import Path
import shutil

from myagent.agent import AgentLoop, ContextBudget, ContextBuilder, ConversationSummaryConfig
from myagent.bus import InboundMessage, MessageBus
from myagent.memory import MarkdownMemoryStore
from myagent.providers.base import ProviderResponse, ToolCall
from myagent.tracing import JsonlTraceStore


def make_message(content: str = "hello") -> InboundMessage:
    return InboundMessage(
        channel="cli",
        sender_id="local-user",
        chat_id="default",
        content=content,
    )


def make_workspace(name: str) -> Path:
    root = Path(".test-workspaces") / "agent-memory" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def read_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class CapturingProvider:
    def __init__(self) -> None:
        self.seen_messages = []
        self.calls = 0

    async def generate(self, messages):
        return '{"items":[]}'

    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        self.calls += 1
        self.seen_messages.append(messages)
        if self.calls == 1:
            return ProviderResponse(
                tool_calls=[
                    ToolCall(
                        id="memory-call-1",
                        name="memory_remember",
                        arguments={
                            "content": "User prefers documentation-first changes.",
                            "section": "Always",
                            "tags": ["workflow"],
                        },
                    )
                ]
            )
        return ProviderResponse(content="ok")


async def test_agent_loop_exposes_memory_remember_tool() -> None:
    root = make_workspace("remember")
    provider = CapturingProvider()
    bus = MessageBus()
    agent = AgentLoop(
        bus,
        provider=provider,
        markdown_memory_store=MarkdownMemoryStore(root / "memory"),
        trace_store=JsonlTraceStore(root / "traces"),
    )

    await bus.publish_inbound(make_message("Remember that I prefer documentation-first changes."))
    await agent.process_next()

    memory_text = (root / "memory" / "MEMORY.md").read_text(encoding="utf-8")
    events = read_events(root / "traces" / "cli_default.jsonl")
    event_names = [event["event"] for event in events]

    assert "User prefers documentation-first changes." in memory_text
    assert "tool_call" in event_names
    assert "tool_result" in event_names
    assert events[[event["event"] for event in events].index("tool_call")]["data"]["tool_name"] == (
        "memory_remember"
    )


class PreContextExtractingProvider:
    def __init__(self) -> None:
        self.generate_calls = []
        self.response_messages = []

    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        self.response_messages.append(messages)
        return ProviderResponse(content="ok")

    async def generate(self, messages):
        self.generate_calls.append(messages)
        if "memory extractor" in messages[0]["content"]:
            return json.dumps(
                {
                    "items": [
                        {
                            "content": "User prefers documentation-first implementation.",
                            "target": "archive",
                            "importance": 3,
                            "tags": ["workflow"],
                        }
                    ]
                }
            )
        return "- Earlier context: user prefers documentation-first implementation."


async def test_agent_loop_flushes_memory_before_pre_context_summary() -> None:
    root = make_workspace("pre-context-flush")
    bus = MessageBus()
    provider = PreContextExtractingProvider()
    context_builder = ContextBuilder(
        identity="You are MyAgent.",
        runtime_environment="",
        delegation_policy=None,
        budget=ContextBudget(
            max_prompt_tokens=120,
            chars_per_token=1,
            raw_history_token_limit=80,
            raw_history_target_tokens=40,
        ),
    )
    agent = AgentLoop(
        bus,
        provider=provider,
        context_builder=context_builder,
        markdown_memory_store=MarkdownMemoryStore(root / "memory"),
        trace_store=JsonlTraceStore(root / "traces"),
        conversation_summary_config=ConversationSummaryConfig(
            keep_recent_messages=2,
        ),
        start_cron=False,
    )
    agent.session_history.raw["cli:default"] = [
        {"role": "user", "content": "old preference " + ("docs first " * 8)},
        {"role": "assistant", "content": "old answer " + ("implementation notes " * 8)},
        {"role": "user", "content": "recent question"},
        {"role": "assistant", "content": "recent answer"},
    ]

    await bus.publish_inbound(make_message("continue"))
    await agent.process_next()

    archive_files = list((root / "memory" / "archive").glob("*.md"))
    archive_text = archive_files[0].read_text(encoding="utf-8")
    events = read_events(root / "traces" / "cli_default.jsonl")
    event_names = [event["event"] for event in events]
    state = agent.session_history.summaries.get("cli:default")
    final_history = provider.response_messages[-1][1:-1]

    assert "User prefers documentation-first implementation." in archive_text
    assert state is not None
    assert state.summarized_message_count == 0
    assert agent.session_history.raw["cli:default"] == [
        {"role": "user", "content": "recent question"},
        {"role": "assistant", "content": "recent answer"},
        {"role": "user", "content": "continue"},
        {"role": "assistant", "content": "ok"},
    ]
    assert {"role": "user", "content": "recent question"} in final_history
    assert {"role": "assistant", "content": "recent answer"} in final_history
    assert not any("old preference" in str(message.get("content", "")) for message in final_history)
    assert "memory_candidates_saved" in event_names
    assert "conversation_summary_updated" in event_names


class NoExtractionProvider:
    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        return ProviderResponse(content="ok")

    async def generate(self, messages):
        return json.dumps({"items": []})


async def test_agent_loop_does_not_run_post_turn_memory_extractor() -> None:
    root = make_workspace("no-post-turn-extract")
    bus = MessageBus()
    agent = AgentLoop(
        bus,
        provider=NoExtractionProvider(),
        markdown_memory_store=MarkdownMemoryStore(root / "memory"),
        trace_store=JsonlTraceStore(root / "traces"),
        start_cron=False,
    )

    await bus.publish_inbound(make_message("I prefer docs first, then implementation."))
    await agent.process_next()

    archive_files = list((root / "memory" / "archive").glob("*.md"))
    events = read_events(root / "traces" / "cli_default.jsonl")

    assert archive_files == []
    assert "memory_candidates_saved" not in [event["event"] for event in events]


class MemoryCompressionProvider:
    def __init__(self) -> None:
        self.generate_calls = []
        self.response_messages = []

    async def generate(self, messages):
        self.generate_calls.append(messages)
        return "# Memory\n\n## Always\n\n- Compact preference.\n\n## Now\n\n- Compact project state."

    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        self.response_messages.append(messages)
        return ProviderResponse(content="ok")


async def test_agent_loop_compresses_visible_memory_before_context() -> None:
    root = make_workspace("visible-memory-compression")
    store = MarkdownMemoryStore(root / "memory")
    store.ensure_layout()
    store.memory_path.write_text(
        "# Memory\n\n## Always\n\n"
        + "- very large stable preference " * 20
        + "\n\n## Now\n\n"
        + "- very large project state " * 20
        + "\n",
        encoding="utf-8",
    )
    bus = MessageBus()
    provider = MemoryCompressionProvider()
    context_builder = ContextBuilder(
        identity="You are MyAgent.",
        runtime_environment="",
        delegation_policy=None,
        budget=ContextBudget(
            chars_per_token=1,
            memory_token_limit=120,
            max_compression_rounds=2,
        ),
    )
    agent = AgentLoop(
        bus,
        provider=provider,
        context_builder=context_builder,
        markdown_memory_store=store,
        trace_store=JsonlTraceStore(root / "traces"),
        start_cron=False,
    )

    await bus.publish_inbound(make_message("hello"))
    await agent.process_next()

    memory_text = store.memory_path.read_text(encoding="utf-8")
    events = read_events(root / "traces" / "cli_default.jsonl")
    event_names = [event["event"] for event in events]

    assert "Compact preference." in memory_text
    assert "very large stable preference" not in memory_text
    assert "memory_compressed" in event_names
    assert "# Always Memory" in provider.response_messages[0][0]["content"]
    assert "Compact preference." in provider.response_messages[0][0]["content"]
