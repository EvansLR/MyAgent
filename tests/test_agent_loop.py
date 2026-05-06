from pathlib import Path
import shutil

from myagent.agent import AgentLoop
from myagent.bus import InboundMessage, MessageBus
from myagent.providers.base import ProviderResponse, ToolCall
from myagent.providers import EchoProvider
from myagent.tools import create_default_registry


def make_message(content: str = "hello") -> InboundMessage:
    return InboundMessage(
        channel="cli",
        sender_id="local-user",
        chat_id="default",
        content=content,
    )


def make_workspace(name: str) -> Path:
    root = Path(".test-workspaces") / "agent-loop" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


async def test_echo_provider_replies_with_input() -> None:
    provider = EchoProvider()

    result = await provider.generate([{"role": "user", "content": "hello"}])

    assert result == "Echo: hello"


async def test_agent_loop_processes_one_message() -> None:
    bus = MessageBus()
    agent = AgentLoop(bus, provider=EchoProvider())
    inbound = make_message("hello")

    await bus.publish_inbound(inbound)
    outbound = await agent.process_next()

    assert outbound.channel == "cli"
    assert outbound.chat_id == "default"
    assert outbound.content == "Echo: hello"
    assert await bus.consume_outbound() == outbound


async def test_agent_loop_adds_turn_to_history() -> None:
    bus = MessageBus()
    agent = AgentLoop(bus, provider=EchoProvider())
    inbound = make_message("hello")

    await bus.publish_inbound(inbound)
    await agent.process_next()

    assert agent.history_for(inbound.session_key) == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "Echo: hello"},
    ]


class ToolCallingProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.seen_tools: list[dict[str, object]] | None = None
        self.seen_messages = []

    async def generate(self, messages):
        return "fallback"

    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        self.calls += 1
        self.seen_tools = tools
        self.seen_messages.append(messages)
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
        return ProviderResponse(content="The file says hello.")


async def test_agent_loop_executes_tool_calls() -> None:
    workspace = make_workspace("tool-calls")
    (workspace / "note.txt").write_text("hello from tool", encoding="utf-8")
    bus = MessageBus()
    provider = ToolCallingProvider()
    agent = AgentLoop(
        bus,
        provider=provider,
        tool_registry=create_default_registry(workspace),
    )

    await bus.publish_inbound(make_message("read note.txt"))
    outbound = await agent.process_next()

    assert outbound.content == "The file says hello."
    status = await bus.consume_outbound()
    final = await bus.consume_outbound()
    assert status.metadata["kind"] == "status"
    assert status.content == "Using tool: read_file path=note.txt"
    assert final == outbound
    assert provider.calls == 2
    assert provider.seen_tools is not None
    assert provider.seen_tools[0]["type"] == "function"
    second_call_messages = provider.seen_messages[1]
    assert second_call_messages[-1]["role"] == "tool"
    assert "hello from tool" in second_call_messages[-1]["content"]


class ReasoningToolCallingProvider(ToolCallingProvider):
    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        self.calls += 1
        self.seen_tools = tools
        self.seen_messages.append(messages)
        if self.calls == 1:
            return ProviderResponse(
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="read_file",
                        arguments={"path": "note.txt"},
                    )
                ],
                extra_message_fields={"reasoning_content": "thinking text"},
            )
        return ProviderResponse(content="Done.")


async def test_agent_loop_preserves_provider_specific_tool_call_fields() -> None:
    workspace = make_workspace("reasoning-tool-calls")
    (workspace / "note.txt").write_text("hello from tool", encoding="utf-8")
    bus = MessageBus()
    provider = ReasoningToolCallingProvider()
    agent = AgentLoop(
        bus,
        provider=provider,
        tool_registry=create_default_registry(workspace),
    )

    await bus.publish_inbound(make_message("read note.txt"))
    await agent.process_next()

    assistant_message = provider.seen_messages[1][-2]
    assert assistant_message["role"] == "assistant"
    assert assistant_message["reasoning_content"] == "thinking text"


class FailingProvider:
    async def generate(self, messages):
        raise RuntimeError("provider down")

    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        raise RuntimeError("provider down")


async def test_agent_loop_returns_error_message_when_provider_fails() -> None:
    bus = MessageBus()
    agent = AgentLoop(bus, provider=FailingProvider())

    await bus.publish_inbound(make_message("hello"))
    outbound = await agent.process_next()

    assert outbound.content == "Error: provider down"


def test_agent_loop_exposes_lock_state() -> None:
    agent = AgentLoop(MessageBus(), provider=EchoProvider())

    assert agent.locked is False


def test_agent_loop_stop_marks_not_running() -> None:
    agent = AgentLoop(MessageBus(), provider=EchoProvider())
    agent._running = True

    agent.stop()

    assert agent.running is False
