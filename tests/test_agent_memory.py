import json
from pathlib import Path
import shutil

from myagent.agent import AgentLoop
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
                        name="memory_append_daily",
                        arguments={
                            "note": "用户正在准备 Java 后端面试。",
                            "tags": ["interview"],
                            "importance": 4,
                        },
                    )
                ]
            )
        return ProviderResponse(content="ok")


async def test_agent_loop_exposes_memory_tool_and_writes_daily_memory() -> None:
    root = make_workspace("save")
    provider = CapturingProvider()
    bus = MessageBus()
    agent = AgentLoop(
        bus,
        provider=provider,
        markdown_memory_store=MarkdownMemoryStore(root / "memory"),
        trace_store=JsonlTraceStore(root / "traces"),
    )

    await bus.publish_inbound(make_message("记一下：我正在准备 Java 后端面试。"))
    await agent.process_next()

    daily_files = list((root / "memory" / "daily").glob("*.md"))
    daily_text = daily_files[0].read_text(encoding="utf-8")
    events = read_events(root / "traces" / "cli_default.jsonl")
    event_names = [event["event"] for event in events]

    assert "用户正在准备 Java 后端面试。" in daily_text
    assert "tool_call" in event_names
    assert "tool_result" in event_names
    assert events[[event["event"] for event in events].index("tool_call")]["data"]["tool_name"] == (
        "memory_append_daily"
    )


class ExtractingProvider:
    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        return ProviderResponse(content="明白。")

    async def generate(self, messages):
        return json.dumps(
            {
                "items": [
                    {
                        "content": "用户偏好先写设计文档再实现代码。",
                        "target": "daily",
                        "importance": 3,
                        "tags": ["workflow"],
                    }
                ]
            },
            ensure_ascii=False,
        )


async def test_agent_loop_runs_post_turn_memory_extractor() -> None:
    root = make_workspace("extract")
    bus = MessageBus()
    agent = AgentLoop(
        bus,
        provider=ExtractingProvider(),
        markdown_memory_store=MarkdownMemoryStore(root / "memory"),
        trace_store=JsonlTraceStore(root / "traces"),
    )

    await bus.publish_inbound(make_message("我更喜欢先写设计文档，再实现代码。"))
    await agent.process_next()

    daily_files = list((root / "memory" / "daily").glob("*.md"))
    daily_text = daily_files[0].read_text(encoding="utf-8")
    events = read_events(root / "traces" / "cli_default.jsonl")

    assert "用户偏好先写设计文档再实现代码。" in daily_text
    assert "memory_candidates_saved" in [event["event"] for event in events]

