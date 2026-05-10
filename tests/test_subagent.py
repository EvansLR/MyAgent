import json
from pathlib import Path
import shutil

from myagent.agent import AgentLoop
from myagent.agent.subagent import (
    DelegateTaskTool,
    SubAgentRunner,
    create_subagent_registry,
    get_subagent_profile,
)
from myagent.bus import InboundMessage, MessageBus
from myagent.providers.base import ProviderResponse, ToolCall
from myagent.skills import SkillRegistry
from myagent.tools import ToolRegistry, create_default_registry
from myagent.tools.base import Tool
from myagent.tracing import JsonlTraceStore


def make_workspace(name: str) -> Path:
    root = Path(".test-workspaces") / "subagent" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def make_message(content: str = "delegate this") -> InboundMessage:
    return InboundMessage(
        channel="cli",
        sender_id="local-user",
        chat_id="default",
        content=content,
    )


class WriteLikeTool(Tool):
    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Fake write tool that should not be delegated."

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self) -> str:
        return "wrote"


class SubagentProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.seen_tools: list[list[dict]] = []
        self.seen_messages: list[list[dict]] = []

    async def generate(self, messages):
        return "fallback"

    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        self.calls += 1
        self.seen_tools.append(tools or [])
        self.seen_messages.append(messages)
        if self.calls == 1:
            return ProviderResponse(
                tool_calls=[
                    ToolCall(
                        id="child-call-1",
                        name="read_file",
                        arguments={"path": "note.txt"},
                    )
                ]
            )
        return ProviderResponse(content="Child summary: note says hello.")


async def test_subagent_runner_uses_restricted_tools() -> None:
    workspace = make_workspace("runner")
    (workspace / "note.txt").write_text("hello from child", encoding="utf-8")
    parent_registry = create_default_registry(workspace)
    parent_registry.register(WriteLikeTool())
    child_registry = create_subagent_registry(parent_registry)
    provider = SubagentProvider()
    runner = SubAgentRunner(provider=provider, tool_registry=child_registry)

    result = await runner.run(task="Read note.txt and summarize it.")

    assert result == "Child summary: note says hello."
    assert provider.calls == 2
    assert child_registry.tool_names == ["list_dir", "read_file", "web_search", "web_fetch"]
    first_tools = [tool["function"]["name"] for tool in provider.seen_tools[0]]
    assert first_tools == ["list_dir", "read_file", "web_search", "web_fetch"]
    assert provider.seen_messages[1][-1]["role"] == "tool"
    assert "hello from child" in provider.seen_messages[1][-1]["content"]


async def test_delegate_task_tool_returns_formatted_subagent_result() -> None:
    workspace = make_workspace("tool")
    (workspace / "note.txt").write_text("hello from delegated tool", encoding="utf-8")
    registry = create_default_registry(workspace)
    provider = SubagentProvider()
    tool = DelegateTaskTool(provider=provider, parent_registry=registry)

    result = await tool.execute(task="Read note.txt.", agent_type="researcher")

    assert "SubAgent task" in result
    assert "profile: researcher" in result
    assert "task: Read note.txt." in result
    assert "Child summary: note says hello." in result


class MainDelegatingProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.seen_tools: list[list[dict]] = []

    async def generate(self, messages):
        return "fallback"

    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        self.calls += 1
        self.seen_tools.append(tools or [])
        if self.calls == 1:
            return ProviderResponse(
                tool_calls=[
                    ToolCall(
                        id="main-call-1",
                        name="delegate_task",
                        arguments={
                            "task": "Read note.txt and summarize it.",
                            "agent_type": "researcher",
                            "reason": "Need isolated file reading.",
                        },
                    )
                ]
            )
        if self.calls == 2:
            return ProviderResponse(
                tool_calls=[
                    ToolCall(
                        id="child-call-1",
                        name="read_file",
                        arguments={"path": "note.txt"},
                    )
                ]
            )
        if self.calls == 3:
            return ProviderResponse(content="Child summary: note says hello.")
        return ProviderResponse(content="Main answer with delegated result.")


class MainSkillThenDelegatingProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.seen_messages: list[list[dict]] = []

    async def generate(self, messages):
        return "fallback"

    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        self.calls += 1
        self.seen_messages.append(messages)
        if self.calls == 1:
            return ProviderResponse(
                tool_calls=[
                    ToolCall(
                        id="skill-call-1",
                        name="skill_get",
                        arguments={"skill_id": "frontend-design"},
                    )
                ]
            )
        if self.calls == 2:
            return ProviderResponse(
                tool_calls=[
                    ToolCall(
                        id="delegate-call-1",
                        name="delegate_task",
                        arguments={
                            "task": "Review the page plan.",
                            "agent_type": "reviewer",
                            "reason": "Check the active design workflow.",
                        },
                    )
                ]
            )
        if self.calls == 3:
            return ProviderResponse(content="Child reviewed the page plan.")
        return ProviderResponse(content="Main answer with skill-aware delegated result.")


async def test_agent_loop_registers_and_executes_delegate_task() -> None:
    root = make_workspace("agent-loop")
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "note.txt").write_text("hello from agent loop", encoding="utf-8")
    provider = MainDelegatingProvider()
    bus = MessageBus()
    agent = AgentLoop(
        bus,
        provider=provider,
        tool_registry=create_default_registry(workspace),
        trace_store=JsonlTraceStore(root / "traces"),
    )

    await bus.publish_inbound(make_message("delegate reading note"))
    outbound = await agent.process_next()

    assert outbound.content == "Main answer with delegated result."
    status = await bus.consume_outbound()
    final = await bus.consume_outbound()
    assert status.content.startswith("Calling tool: delegate_task")
    assert final == outbound
    main_tool_names = [tool["function"]["name"] for tool in provider.seen_tools[0]]
    child_tool_names = [tool["function"]["name"] for tool in provider.seen_tools[1]]
    assert "delegate_task" in main_tool_names
    assert child_tool_names == ["list_dir", "read_file", "web_search", "web_fetch"]

    events = [
        json.loads(line)
        for line in (root / "traces" / "cli_default.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    event_names = [event["event"] for event in events]
    assert "subagent_tool_call" in event_names
    assert "subagent_tool_result" in event_names

    subagent_start = next(event for event in events if event["event"] == "subagent_start")
    child_tool_call = next(event for event in events if event["event"] == "subagent_tool_call")
    child_tool_result = next(event for event in events if event["event"] == "subagent_tool_result")
    assert child_tool_call["data"]["subagent_task_id"] == subagent_start["data"]["subagent_task_id"]
    assert child_tool_result["data"]["subagent_task_id"] == subagent_start["data"]["subagent_task_id"]
    assert child_tool_call["data"]["parent_turn_id"] == subagent_start["turn_id"]
    assert child_tool_result["data"]["parent_tool_call_id"] == "main-call-1"
    assert subagent_start["data"]["delegation_reason"] == "Need isolated file reading."
    assert subagent_start["data"]["delegation_mode"] == "explicit"
    assert child_tool_result["data"]["delegation_reason"] == "Need isolated file reading."
    assert child_tool_call["data"]["tool_name"] == "read_file"
    assert "hello from agent loop" in child_tool_result["data"]["result_preview"]


async def test_delegate_task_receives_compact_parent_active_skill_context() -> None:
    root = make_workspace("active-skill-context")
    workspace = root / "workspace"
    skills_root = root / "skills"
    workspace.mkdir()
    skill_path = skills_root / "frontend-design" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text(
        "\n".join(
            [
                "---",
                "name: frontend-design",
                "description: Build polished frontend interfaces.",
                "---",
                "",
                "# Frontend Design",
            ]
        ),
        encoding="utf-8",
    )
    provider = MainSkillThenDelegatingProvider()
    bus = MessageBus()
    agent = AgentLoop(
        bus,
        provider=provider,
        tool_registry=create_default_registry(workspace),
        skill_registry=SkillRegistry.from_directory(skills_root),
        trace_store=JsonlTraceStore(root / "traces"),
    )

    await bus.publish_inbound(make_message("use the frontend skill, then delegate review"))
    outbound = await agent.process_next()

    assert outbound.content == "Main answer with skill-aware delegated result."
    child_messages = provider.seen_messages[2]
    assert "# Parent Active Skills" in child_messages[1]["content"]
    assert "frontend-design" in child_messages[1]["content"]
    assert "loaded_by_skill_get" in child_messages[1]["content"]

    events = [
        json.loads(line)
        for line in (root / "traces" / "cli_default.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    subagent_start = next(event for event in events if event["event"] == "subagent_start")
    assert subagent_start["data"]["inherited_active_skills"] == ["frontend-design"]


def test_create_subagent_registry_allows_read_only_file_and_web_tools() -> None:
    registry = create_default_registry(make_workspace("restricted"))
    registry.register(WriteLikeTool())
    registry.register(DelegateTaskTool(provider=SubagentProvider(), parent_registry=registry))

    child_registry = create_subagent_registry(
        registry,
        get_subagent_profile("researcher").allowed_tools,
    )

    assert child_registry.tool_names == ["list_dir", "read_file", "web_search", "web_fetch"]
    assert "write_file" not in child_registry.tool_names
    assert "delegate_task" not in child_registry.tool_names


def test_subagent_profiles_have_distinct_tool_allowlists() -> None:
    registry = create_default_registry(make_workspace("profile-tools"))
    registry.register(WriteLikeTool())
    registry.register(DelegateTaskTool(provider=SubagentProvider(), parent_registry=registry))

    researcher = create_subagent_registry(
        registry,
        get_subagent_profile("researcher").allowed_tools,
    )
    reviewer = create_subagent_registry(
        registry,
        get_subagent_profile("reviewer").allowed_tools,
    )
    interviewer = create_subagent_registry(
        registry,
        get_subagent_profile("interviewer").allowed_tools,
    )

    assert researcher.tool_names == ["list_dir", "read_file", "web_search", "web_fetch"]
    assert reviewer.tool_names == ["list_dir", "read_file"]
    assert interviewer.tool_names == ["web_search", "web_fetch"]
    for child_registry in (researcher, reviewer, interviewer):
        assert "write_file" not in child_registry.tool_names
        assert "delegate_task" not in child_registry.tool_names
