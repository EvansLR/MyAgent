import json
from pathlib import Path
import shutil

from myagent.agent import AgentLoop
from myagent.bus import InboundMessage, MessageBus

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
    )

    await bus.publish_inbound(make_message("hello"))
    await agent.process_next()

    events = read_events(root / "cli_default.jsonl")
    event_names = [event["event"] for event in events]

    assert event_names == [
        "user_message",
        "workspace_loaded",
        "context_built",
        "llm_request",
        "llm_response",
        "final_answer",
        "turn_completed",
    ]
    assert events[0]["data"]["content"] == "hello"
    assert events[1]["event"] == "workspace_loaded"
    context = events[2]["data"]["context"]
    assert context["message_count"] == 2
    assert context["history"]["included_messages"] == 0
    assert context["sections"][0]["name"] == "Identity"
    assert context["sections"][0]["tier"] == "protected"
    assert events[-2]["data"]["content_preview"] == "Echo: hello"
    assert events[-1]["data"]["stop_reason"] == "final_output"
    assert events[-1]["data"]["iterations"] == 1
    assert events[-1]["data"]["tool_call_count"] == 0


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
    completed = next(event for event in events if event["event"] == "turn_completed")
    assert completed["data"]["stop_reason"] == "final_output"
    assert completed["data"]["iterations"] == 2
    assert completed["data"]["tool_call_count"] == 1


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
    )

    await bus.publish_inbound(make_message("hello"))
    await agent.process_next()

    events = read_events(root / "cli_default.jsonl")
    error = next(event for event in events if event["event"] == "error")
    assert error["data"]["type"] == "RuntimeError"
    assert error["data"]["message"] == "provider down"
    completed = next(event for event in events if event["event"] == "turn_completed")
    assert completed["data"]["stop_reason"] == "provider_error"


class RepeatingToolProvider:
    async def generate(self, messages):
        return "fallback"

    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        return ProviderResponse(
            tool_calls=[
                ToolCall(
                    id="repeat-call",
                    name="read_file",
                    arguments={"path": "note.txt"},
                )
            ]
        )


async def test_agent_loop_records_max_iteration_stop_and_repeated_tool_warning() -> None:
    root = make_workspace("max-iterations")
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "note.txt").write_text("loop evidence", encoding="utf-8")
    bus = MessageBus()
    agent = AgentLoop(
        bus,
        provider=RepeatingToolProvider(),
        tool_registry=create_default_registry(workspace),
        trace_store=JsonlTraceStore(root / "traces"),
        max_tool_iterations=3,
    )

    await bus.publish_inbound(make_message("read note repeatedly"))
    outbound = await agent.process_next()

    assert "Tool call limit reached" in outbound.content
    events = read_events(root / "traces" / "cli_default.jsonl")
    completed = next(event for event in events if event["event"] == "turn_completed")
    assert completed["data"]["stop_reason"] == "max_tool_iterations"
    assert completed["data"]["iterations"] == 3
    assert completed["data"]["tool_call_count"] == 3
    assert completed["data"]["tool_error_count"] == 0
    assert "repeated_tool_call:read_file" in completed["data"]["warnings"]
