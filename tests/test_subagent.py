from pathlib import Path
import shutil

from myagent.agent import AgentLoop
from myagent.agent.subagent import DelegateTaskTool, SubAgentRunner, create_subagent_registry
from myagent.bus import InboundMessage, MessageBus
from myagent.providers.base import ProviderResponse, ToolCall
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
    assert child_registry.tool_names == ["list_dir", "read_file"]
    first_tools = [tool["function"]["name"] for tool in provider.seen_tools[0]]
    assert first_tools == ["list_dir", "read_file"]
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
    assert status.content.startswith("正在调用工具：delegate_task")
    assert final == outbound
    main_tool_names = [tool["function"]["name"] for tool in provider.seen_tools[0]]
    child_tool_names = [tool["function"]["name"] for tool in provider.seen_tools[1]]
    assert "delegate_task" in main_tool_names
    assert child_tool_names == ["list_dir", "read_file"]


def test_create_subagent_registry_excludes_delegate_task_and_write_tools() -> None:
    registry = ToolRegistry()
    default_registry = create_default_registry(make_workspace("restricted"))
    registry.register(default_registry.get("list_dir"))
    registry.register(default_registry.get("read_file"))
    registry.register(WriteLikeTool())
    registry.register(DelegateTaskTool(provider=SubagentProvider(), parent_registry=registry))

    child_registry = create_subagent_registry(registry)

    assert child_registry.tool_names == ["list_dir", "read_file"]
