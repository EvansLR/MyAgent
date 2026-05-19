from pathlib import Path
import shutil

from myagent.agent import AgentLoop, ContextBudget, ContextBuilder, ConversationSummaryConfig
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
    provider = ConversationSummaryProvider()
    agent = AgentLoop(bus, provider=provider)

    await bus.publish_inbound(make_message("hello"))
    await agent.process_next()
    await bus.publish_inbound(make_message("again"))
    await agent.process_next()

    second_call_messages = provider.seen_messages[1]
    assert {"role": "user", "content": "hello"} in second_call_messages
    assert {"role": "assistant", "content": "answer 1"} in second_call_messages


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
    assert status.content == "Calling tool: read_file path=note.txt"
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


class LargeToolResultProvider(ToolCallingProvider):
    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        self.calls += 1
        self.seen_tools = tools
        self.seen_messages.append(messages)
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


async def test_agent_loop_keeps_tool_result_visible_before_next_model_call() -> None:
    workspace = make_workspace("large-tool-result")
    (workspace / "large.txt").write_text("x" * 200, encoding="utf-8")
    bus = MessageBus()
    provider = LargeToolResultProvider()
    context_builder = ContextBuilder(
        identity="ID",
        delegation_policy=None,
        budget=ContextBudget(chars_per_token=1),
    )
    agent = AgentLoop(
        bus,
        provider=provider,
        context_builder=context_builder,
        tool_registry=create_default_registry(workspace),
    )

    await bus.publish_inbound(make_message("read large file"))
    await agent.process_next()

    second_call_messages = provider.seen_messages[1]
    tool_message = second_call_messages[-1]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call-large"
    assert "x" * 200 in tool_message["content"]
    assert "[Tool result compacted]" not in tool_message["content"]


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


class ConversationSummaryProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.seen_messages = []
        self.summary_prompts = []

    async def generate(self, messages):
        self.summary_prompts.append(messages)
        return "- Earlier context: user prefers lightweight summaries."

    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        self.calls += 1
        self.seen_messages.append(messages)
        return ProviderResponse(content=f"answer {self.calls}")


async def test_agent_loop_updates_summary_before_context_when_history_would_trim() -> None:
    bus = MessageBus()
    provider = ConversationSummaryProvider()
    context_builder = ContextBuilder(
        identity="You are MyAgent.",
        runtime_environment="",
        delegation_policy=None,
        budget=ContextBudget(max_prompt_tokens=400, chars_per_token=1, history_token_ratio=0.0),
    )
    agent = AgentLoop(
        bus,
        provider=provider,
        context_builder=context_builder,
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
        {"role": "user", "content": "first " + ("large " * 40)},
        {"role": "assistant", "content": "answer 1 " + ("large " * 40)},
        {"role": "user", "content": "second"},
        {"role": "assistant", "content": "answer 2"},
    ]

    await bus.publish_inbound(make_message("third"))
    await agent.process_next()

    state = agent._conversation_summaries.get("cli:default")
    assert state is not None
    assert state.summarized_message_count == 2
    assert provider.summary_prompts

    call_system = provider.seen_messages[0][0]["content"]
    assert "# Conversation Summary" in call_system
    assert "lightweight summaries" in call_system
    call_history = provider.seen_messages[0][1:-1]
    assert not any("first" in str(message.get("content", "")) for message in call_history)
    assert not any("answer 1" in str(message.get("content", "")) for message in call_history)
    assert {"role": "user", "content": "second"} in call_history
    assert {"role": "assistant", "content": "answer 2"} in call_history


async def test_agent_loop_forces_summary_under_context_pressure_even_with_few_new_messages() -> None:
    bus = MessageBus()
    provider = ConversationSummaryProvider()
    context_builder = ContextBuilder(
        identity="You are MyAgent.",
        runtime_environment="",
        delegation_policy=None,
        budget=ContextBudget(max_prompt_tokens=400, chars_per_token=1, history_token_ratio=0.0),
    )
    agent = AgentLoop(
        bus,
        provider=provider,
        context_builder=context_builder,
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
        {"role": "user", "content": "first " + ("large " * 40)},
        {"role": "assistant", "content": "answer 1 " + ("large " * 40)},
        {"role": "user", "content": "second"},
        {"role": "assistant", "content": "answer 2"},
    ]

    await bus.publish_inbound(make_message("third"))
    await agent.process_next()

    state = agent._conversation_summaries.get("cli:default")
    assert state is not None
    assert state.summarized_message_count == 2
    assert provider.summary_prompts


def test_agent_loop_exposes_lock_state() -> None:
    agent = AgentLoop(MessageBus(), provider=EchoProvider())

    assert agent.locked is False


def test_agent_loop_stop_marks_not_running() -> None:
    agent = AgentLoop(MessageBus(), provider=EchoProvider())
    agent._running = True

    agent.stop()

    assert agent.running is False
