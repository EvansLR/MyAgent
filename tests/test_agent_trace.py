import json
from pathlib import Path
import shutil

from myagent.agent import AgentLoop
from myagent.bus import InboundMessage, MessageBus
from myagent.memory import JsonlMemoryStore
from myagent.providers import EchoProvider
from myagent.providers.base import ProviderResponse, ToolCall
from myagent.tools import create_default_registry
from myagent.tracing import JsonlTraceStore


def make_message(content: str = "hello") -> InboundMessage:
    return InboundMessage(
        channel="cli",
        sender_id="local-user",
        chat_id="default",
        content=content,
    )


def make_workspace(name: str) -> Path:
    root = Path(".test-workspaces") / "agent-trace" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def read_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


async def test_agent_loop_records_basic_trace_events() -> None:
    root = make_workspace("basic")
    bus = MessageBus()
    agent = AgentLoop(
        bus,
        provider=EchoProvider(),
        trace_store=JsonlTraceStore(root),
        memory_store=JsonlMemoryStore(root / "memory.jsonl"),
    )

    await bus.publish_inbound(make_message("hello"))
    await agent.process_next()

    events = read_events(root / "cli_default.jsonl")
    event_names = [event["event"] for event in events]

    assert event_names == [
        "user_message",
        "context_built",
        "llm_request",
        "llm_response",
        "final_answer",
    ]
    assert events[0]["data"]["content"] == "hello"
    context = events[1]["data"]["context"]
    assert context["message_count"] == 2
    assert context["history"]["included_messages"] == 0
    assert context["sections"][0]["name"] == "Identity"
    assert context["sections"][0]["tier"] == "protected"
    assert events[-1]["data"]["content_preview"] == "Echo: hello"


class TraceToolProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, messages):
        return "fallback"

    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        self.calls += 1
        if self.calls == 1:
            return ProviderResponse(
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="read_file",
                        arguments={"path": "note.txt"},
                    )
                ]
            )
        return ProviderResponse(content="Done.")


async def test_agent_loop_records_tool_trace_events() -> None:
    root = make_workspace("tool")
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "note.txt").write_text("hello from file", encoding="utf-8")
    bus = MessageBus()
    agent = AgentLoop(
        bus,
        provider=TraceToolProvider(),
        tool_registry=create_default_registry(workspace),
        trace_store=JsonlTraceStore(root / "traces"),
    )

    await bus.publish_inbound(make_message("read note"))
    await agent.process_next()

    events = read_events(root / "traces" / "cli_default.jsonl")
    event_names = [event["event"] for event in events]

    assert "tool_call" in event_names
    assert "tool_result" in event_names
    tool_call = next(event for event in events if event["event"] == "tool_call")
    tool_result = next(event for event in events if event["event"] == "tool_result")
    assert tool_call["data"]["tool_name"] == "read_file"
    assert tool_result["data"]["tool_name"] == "read_file"
    assert "hello from file" in tool_result["data"]["result_preview"]


class TraceFailingProvider:
    async def generate(self, messages):
        raise RuntimeError("provider down")

    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        raise RuntimeError("provider down")


async def test_agent_loop_records_error_trace_event() -> None:
    root = make_workspace("error")
    bus = MessageBus()
    agent = AgentLoop(
        bus,
        provider=TraceFailingProvider(),
        trace_store=JsonlTraceStore(root),
        memory_store=JsonlMemoryStore(root / "memory.jsonl"),
    )

    await bus.publish_inbound(make_message("hello"))
    await agent.process_next()

    events = read_events(root / "cli_default.jsonl")
    error = next(event for event in events if event["event"] == "error")
    assert error["data"]["type"] == "RuntimeError"
    assert error["data"]["message"] == "provider down"
