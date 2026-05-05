from myagent.bus import InboundMessage, MessageBus, OutboundMessage


def test_inbound_message_default_session_key() -> None:
    msg = InboundMessage(
        channel="cli",
        sender_id="local-user",
        chat_id="default",
        content="hello",
    )

    assert msg.session_key == "cli:default"


def test_inbound_message_override_session_key() -> None:
    msg = InboundMessage(
        channel="cli",
        sender_id="local-user",
        chat_id="default",
        content="hello",
        session_key_override="custom-session",
    )

    assert msg.session_key == "custom-session"


async def test_message_bus_delivers_inbound_message() -> None:
    bus = MessageBus()
    msg = InboundMessage(
        channel="cli",
        sender_id="local-user",
        chat_id="default",
        content="hello",
    )

    await bus.publish_inbound(msg)

    assert await bus.consume_inbound() == msg


async def test_message_bus_delivers_outbound_message() -> None:
    bus = MessageBus()
    msg = OutboundMessage(channel="cli", chat_id="default", content="hi")

    await bus.publish_outbound(msg)

    assert await bus.consume_outbound() == msg


async def test_message_bus_reports_queue_sizes() -> None:
    bus = MessageBus()
    inbound = InboundMessage(
        channel="cli",
        sender_id="local-user",
        chat_id="default",
        content="hello",
    )
    outbound = OutboundMessage(channel="cli", chat_id="default", content="hi")

    assert bus.inbound_size == 0
    assert bus.outbound_size == 0

    await bus.publish_inbound(inbound)
    await bus.publish_outbound(outbound)

    assert bus.inbound_size == 1
    assert bus.outbound_size == 1

    await bus.consume_inbound()
    await bus.consume_outbound()

    assert bus.inbound_size == 0
    assert bus.outbound_size == 0
