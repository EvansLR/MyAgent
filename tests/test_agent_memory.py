import json
from pathlib import Path
import shutil

from myagent.agent import AgentLoop
from myagent.bus import InboundMessage, MessageBus
from myagent.memory import JsonlMemoryStore
from myagent.providers.base import ProviderResponse
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

    async def generate(self, messages):
        self.seen_messages.append(messages)
        return "ok"

    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        self.seen_messages.append(messages)
        return ProviderResponse(content="ok")


async def test_agent_loop_saves_explicit_memory_and_includes_it_in_context() -> None:
    root = make_workspace("save")
    provider = CapturingProvider()
    bus = MessageBus()
    agent = AgentLoop(
        bus,
        provider=provider,
        memory_store=JsonlMemoryStore(root / "facts.jsonl"),
        trace_store=JsonlTraceStore(root / "traces"),
    )

    await bus.publish_inbound(make_message("记住：我正在准备 Java 后端面试。"))
    await agent.process_next()

    system_prompt = provider.seen_messages[0][0]["content"]
    memories = JsonlMemoryStore(root / "facts.jsonl").list_entries()
    events = read_events(root / "traces" / "cli_default.jsonl")
    event_names = [event["event"] for event in events]

    assert memories[0].content == "我正在准备 Java 后端面试。"
    assert "# Memory" in system_prompt
    assert "我正在准备 Java 后端面试。" in system_prompt
    assert "memory_saved" in event_names
    assert "memory_recalled" in event_names
