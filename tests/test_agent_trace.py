import json
from pathlib import Path
import shutil

from myagent.agent import AgentLoop, ContextBudget, ContextBuilder, ConversationSummaryConfig
from myagent.bus import InboundMessage, MessageBus

from myagent.providers import EchoProvider
from myagent.providers.base import ProviderResponse, ToolCall
from myagent.skills import SkillRegistry
from myagent.skills.entries import SkillEntry
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
        "profile_loaded",
        "context_built",
        "llm_request",
        "llm_response",
        "final_answer",
        "turn_completed",
    ]
    assert events[0]["data"]["content"] == "hello"
    assert events[1]["event"] == "profile_loaded"
    context = events[2]["data"]["context"]
    assert context["message_count"] == 2
    assert context["history"]["included_messages"] == 0
    assert context["sections"][0]["name"] == "Identity"
    assert context["sections"][0]["retention"] == "required"
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


async def test_agent_loop_records_context_dropped_trace_event() -> None:
    root = make_workspace("context-dropped")
    bus = MessageBus()
    skill_registry = SkillRegistry(
        [
            SkillEntry(
                id="large-skill",
                name="large-skill",
                description="Use this skill when " + ("the task is large. " * 80),
                path=Path("skills/large-skill/SKILL.md"),
            )
        ]
    )
    context_builder = ContextBuilder(
        identity="ID",
        delegation_policy=None,
        skill_registry=skill_registry,
        budget=ContextBudget(max_prompt_tokens=20, chars_per_token=4),
    )
    agent = AgentLoop(
        bus,
        provider=EchoProvider(),
        context_builder=context_builder,
        skill_registry=skill_registry,
        trace_store=JsonlTraceStore(root),
    )

    await bus.publish_inbound(make_message("hello"))
    await agent.process_next()

    events = read_events(root / "cli_default.jsonl")
    dropped = next(event for event in events if event["event"] == "context_dropped")
    assert dropped["data"]["max_prompt_tokens"] == 20
    assert dropped["data"]["estimated_tokens_before"] > dropped["data"]["estimated_tokens_after"]
    assert dropped["data"]["dropped_sections"][0]["name"] == "Available Skills"
    assert dropped["data"]["dropped_sections"][0]["reason"] == "budget_exceeded"


class LargeTraceToolProvider:
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
                        id="call-large",
                        name="read_file",
                        arguments={"path": "large.txt"},
                    )
                ]
            )
        return ProviderResponse(content="Done.")


async def test_agent_loop_does_not_compact_tool_result_before_next_call() -> None:
    root = make_workspace("working-context-not-compacted")
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "large.txt").write_text("x" * 200, encoding="utf-8")
    bus = MessageBus()
    context_builder = ContextBuilder(
        identity="ID",
        delegation_policy=None,
        budget=ContextBudget(chars_per_token=1),
    )
    agent = AgentLoop(
        bus,
        provider=LargeTraceToolProvider(),
        context_builder=context_builder,
        tool_registry=create_default_registry(workspace),
        trace_store=JsonlTraceStore(root / "traces"),
    )

    await bus.publish_inbound(make_message("read large file"))
    await agent.process_next()

    events = read_events(root / "traces" / "cli_default.jsonl")
    assert not any(event["event"] == "working_context_compacted" for event in events)


class TraceSummaryProvider:
    def __init__(self, fail_summary: bool = False) -> None:
        self.calls = 0
        self.fail_summary = fail_summary

    async def generate(self, messages):
        if self.fail_summary:
            raise RuntimeError("summary down")
        return "- Folded earlier context into summary."

    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        self.calls += 1
        return ProviderResponse(content=f"answer {self.calls}")


async def test_agent_loop_records_conversation_summary_trace_events() -> None:
    root = make_workspace("conversation-summary-trace")
    bus = MessageBus()
    context_builder = ContextBuilder(
        identity="You are MyAgent.",
        runtime_environment="",
        delegation_policy=None,
        budget=ContextBudget(max_prompt_tokens=100, chars_per_token=1),
    )
    agent = AgentLoop(
        bus,
        provider=TraceSummaryProvider(),
        context_builder=context_builder,
        trace_store=JsonlTraceStore(root),
        conversation_summary_config=ConversationSummaryConfig(
            trigger_messages=100,
            trigger_tokens=None,
            keep_recent_messages=2,
            min_new_messages=6,
        ),
        start_cron=False,
    )
    agent.memory_extractor = None
    agent._history["cli:default"] = [
        {"role": "user", "content": "first " + ("large " * 12)},
        {"role": "assistant", "content": "answer 1 " + ("large " * 12)},
        {"role": "user", "content": "second"},
        {"role": "assistant", "content": "answer 2"},
    ]

    await bus.publish_inbound(make_message("third"))
    await agent.process_next()

    events = read_events(root / "cli_default.jsonl")
    checked = next(event for event in events if event["event"] == "conversation_summary_checked")
    updated = next(event for event in events if event["event"] == "conversation_summary_updated")
    assert checked["data"]["reason"] == "pre_context_budget_pressure"
    assert checked["data"]["new_messages_considered"] == 2
    assert updated["data"]["summarized_message_count_after"] == 2
    assert updated["data"]["summary_chars_after"] > 0

    events = read_events(root / "cli_default.jsonl")
    context_events = [event for event in events if event["event"] == "context_built"]
    assert context_events[-1]["data"]["full_history_messages"] == 4
    assert context_events[-1]["data"]["visible_history_messages"] == 2


async def test_agent_loop_records_conversation_summary_failure_trace() -> None:
    root = make_workspace("conversation-summary-failed")
    bus = MessageBus()
    context_builder = ContextBuilder(
        identity="You are MyAgent.",
        runtime_environment="",
        delegation_policy=None,
        budget=ContextBudget(max_prompt_tokens=100, chars_per_token=1),
    )
    agent = AgentLoop(
        bus,
        provider=TraceSummaryProvider(fail_summary=True),
        context_builder=context_builder,
        trace_store=JsonlTraceStore(root),
        conversation_summary_config=ConversationSummaryConfig(
            trigger_messages=100,
            trigger_tokens=None,
            keep_recent_messages=2,
            min_new_messages=6,
        ),
        start_cron=False,
    )
    agent.memory_extractor = None
    agent._history["cli:default"] = [
        {"role": "user", "content": "first " + ("large " * 12)},
        {"role": "assistant", "content": "answer 1 " + ("large " * 12)},
        {"role": "user", "content": "second"},
        {"role": "assistant", "content": "answer 2"},
    ]

    await bus.publish_inbound(make_message("third"))
    outbound = await agent.process_next()

    events = read_events(root / "cli_default.jsonl")
    assert outbound.content == "answer 1"
    assert not [event for event in events if event["event"] == "conversation_summary_updated"]
    failed = next(event for event in events if event["event"] == "conversation_summary_failed")
    assert failed["data"]["type"] == "RuntimeError"
    assert failed["data"]["message"] == "summary down"
