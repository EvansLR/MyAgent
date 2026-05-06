from myagent.agent import AgentLoop
from myagent.bus import InboundMessage, MessageBus
from myagent.providers import EchoProvider


def make_message(content: str = "hello") -> InboundMessage:
    return InboundMessage(
        channel="cli",
        sender_id="local-user",
        chat_id="default",
        content=content,
    )


async def test_echo_provider_replies_with_input() -> None:
    provider = EchoProvider()

    result = await provider.generate(make_message("hello"))

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


def test_agent_loop_exposes_lock_state() -> None:
    agent = AgentLoop(MessageBus(), provider=EchoProvider())

    assert agent.locked is False


def test_agent_loop_stop_marks_not_running() -> None:
    agent = AgentLoop(MessageBus(), provider=EchoProvider())
    agent._running = True

    agent.stop()

    assert agent.running is False
