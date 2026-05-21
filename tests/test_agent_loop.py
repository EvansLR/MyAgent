from pathlib import Path
import shutil

from myagent.agent import AgentLoop, ContextBudget, ContextBuilder, ConversationSummaryConfig
from myagent.approval import ApprovalRoute
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


class AttachmentToolCallingProvider(ToolCallingProvider):
    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        self.calls += 1
        self.seen_tools = tools
        self.seen_messages.append(messages)
        if self.calls == 1:
            return ProviderResponse(
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="attach_file",
                        arguments={"file_path": "image.png"},
                    )
                ]
            )
        return ProviderResponse(content="I attached the image.")


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


async def test_agent_loop_attaches_files_to_final_reply() -> None:
    workspace = make_workspace("attachments")
    image = workspace / "image.png"
    image.write_bytes(b"fake image")
    bus = MessageBus()
    provider = AttachmentToolCallingProvider()
    agent = AgentLoop(
        bus,
        provider=provider,
        tool_registry=create_default_registry(workspace),
    )

    await bus.publish_inbound(make_message("send me image.png"))
    outbound = await agent.process_next()

    status = await bus.consume_outbound()
    final = await bus.consume_outbound()
    assert status.metadata["kind"] == "status"
    assert final == outbound
    assert outbound.content == "I attached the image."
    assert outbound.media == [str(image.resolve())]


class ApprovalToolCallingProvider(ToolCallingProvider):
    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        self.calls += 1
        self.seen_tools = tools
        self.seen_messages.append(messages)
        if self.calls == 1:
            return ProviderResponse(
                tool_calls=[
                    ToolCall(
                        id="call-approval",
                        name="execute_command",
                        arguments={"command": "unknown-build-tool --list"},
                    )
                ]
            )
        return ProviderResponse(content="Done.")


async def test_agent_loop_routes_tool_approval_through_execution_context() -> None:
    workspace = make_workspace("tool-approval-context")
    bus = MessageBus()
    provider = ApprovalToolCallingProvider()
    approvals: list[tuple[str, ApprovalRoute]] = []

    async def approve(prompt: str, route: ApprovalRoute) -> bool:
        approvals.append((prompt, route))
        return False

    agent = AgentLoop(
        bus,
        provider=provider,
        tool_registry=create_default_registry(workspace),
        approval_callback=approve,
    )

    await bus.publish_inbound(make_message("run risky command"))
    await agent.process_next()

    assert len(approvals) == 1
    prompt, route = approvals[0]
    assert "unknown-build-tool --list" in prompt
    assert route == ApprovalRoute("cli", "default")
    tool_message = provider.seen_messages[1][-1]
    assert "User denied" in tool_message["content"]


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


class LongThenCompressedSummaryProvider(ConversationSummaryProvider):
    async def generate(self, messages):
        self.summary_prompts.append(messages)
        user_prompt = messages[-1]["content"]
        if "Rewrite this conversation summary" in user_prompt:
            return "- Compact summary."
        return "- Long summary " + ("details " * 20)


async def test_agent_loop_updates_summary_before_context_when_history_would_trim() -> None:
    bus = MessageBus()
    provider = ConversationSummaryProvider()
    context_builder = ContextBuilder(
        identity="You are MyAgent.",
        runtime_environment="",
        delegation_policy=None,
        budget=ContextBudget(
            max_prompt_tokens=400,
            chars_per_token=1,
            raw_history_token_limit=120,
            raw_history_target_tokens=40,
        ),
    )
    agent = AgentLoop(
        bus,
        provider=provider,
        context_builder=context_builder,
        conversation_summary_config=ConversationSummaryConfig(
            keep_recent_messages=2,
        ),
        start_cron=False,
    )
    agent.session_history.memory_extractor = None
    agent.session_history.raw["cli:default"] = [
        {"role": "user", "content": "first " + ("large " * 40)},
        {"role": "assistant", "content": "answer 1 " + ("large " * 40)},
        {"role": "user", "content": "second"},
        {"role": "assistant", "content": "answer 2"},
    ]

    await bus.publish_inbound(make_message("third"))
    await agent.process_next()

    state = agent.session_history.summaries.get("cli:default")
    assert state is not None
    assert state.summarized_message_count == 0
    assert provider.summary_prompts
    assert agent.session_history.raw["cli:default"] == [
        {"role": "user", "content": "second"},
        {"role": "assistant", "content": "answer 2"},
        {"role": "user", "content": "third"},
        {"role": "assistant", "content": "answer 1"},
    ]
    assert provider.seen_messages[0][1:-1] == [
        {"role": "user", "content": "second"},
        {"role": "assistant", "content": "answer 2"},
    ]

    call_system = provider.seen_messages[0][0]["content"]
    assert "# Conversation Summary" in call_system
    assert "lightweight summaries" in call_system


async def test_agent_loop_compacts_history_to_target_tokens() -> None:
    bus = MessageBus()
    provider = ConversationSummaryProvider()
    context_builder = ContextBuilder(
        identity="You are MyAgent.",
        runtime_environment="",
        delegation_policy=None,
        budget=ContextBudget(
            max_prompt_tokens=400,
            chars_per_token=1,
            raw_history_token_limit=200,
            raw_history_target_tokens=100,
        ),
    )
    agent = AgentLoop(
        bus,
        provider=provider,
        context_builder=context_builder,
        conversation_summary_config=ConversationSummaryConfig(
            keep_recent_messages=2,
        ),
        start_cron=False,
    )
    agent.session_history.memory_extractor = None
    agent.session_history.raw["cli:default"] = [
        {"role": "user", "content": "first " + ("large " * 40)},
        {"role": "assistant", "content": "answer 1 " + ("large " * 40)},
        {"role": "user", "content": "second"},
        {"role": "assistant", "content": "answer 2"},
    ]

    await bus.publish_inbound(make_message("third"))
    await agent.process_next()

    state = agent.session_history.summaries.get("cli:default")
    assert state is not None
    assert state.summarized_message_count == 0
    assert provider.summary_prompts
    raw_history = provider.seen_messages[0][1:-1]
    raw_history_tokens = sum(len(message["content"]) for message in raw_history)
    assert raw_history_tokens <= 100


async def test_agent_loop_compresses_summary_when_it_exceeds_limit() -> None:
    bus = MessageBus()
    provider = LongThenCompressedSummaryProvider()
    context_builder = ContextBuilder(
        identity="You are MyAgent.",
        runtime_environment="",
        delegation_policy=None,
        budget=ContextBudget(
            chars_per_token=1,
            raw_history_token_limit=120,
            raw_history_target_tokens=40,
            summary_token_limit=40,
            max_compression_rounds=2,
        ),
    )
    agent = AgentLoop(
        bus,
        provider=provider,
        context_builder=context_builder,
        conversation_summary_config=ConversationSummaryConfig(
            keep_recent_messages=2,
        ),
        start_cron=False,
    )
    agent.session_history.memory_extractor = None
    agent.session_history.raw["cli:default"] = [
        {"role": "user", "content": "first " + ("large " * 20)},
        {"role": "assistant", "content": "answer 1 " + ("large " * 20)},
        {"role": "user", "content": "second"},
        {"role": "assistant", "content": "answer 2"},
    ]

    await bus.publish_inbound(make_message("third"))
    await agent.process_next()

    state = agent.session_history.summaries.get("cli:default")
    assert state is not None
    assert state.content == "- Compact summary."
    assert state.estimated_tokens <= 40
    assert len(provider.summary_prompts) == 2


def test_agent_loop_exposes_lock_state() -> None:
    agent = AgentLoop(MessageBus(), provider=EchoProvider())

    assert agent.locked is False


def test_agent_loop_stop_marks_not_running() -> None:
    agent = AgentLoop(MessageBus(), provider=EchoProvider())
    agent._running = True

    agent.stop()

    assert agent.running is False
