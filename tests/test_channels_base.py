"""Tests for BaseChannel abstraction."""

import pytest

from myagent.bus import MessageBus, OutboundMessage
from myagent.channels.base import BaseChannel


class FakeChannel(BaseChannel):
    name = "fake"

    def __init__(self, config, bus):
        super().__init__(config, bus)
        self.started = False
        self.stopped = False
        self.sent: list[OutboundMessage] = []

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def send(self, msg):
        self.sent.append(msg)


@pytest.fixture
def bus():
    return MessageBus()


class TestBaseChannel:
    def test_name_default(self, bus):
        ch = FakeChannel({}, bus)
        assert ch.name == "fake"

    @pytest.mark.asyncio
    async def test_handle_message_publishes_inbound(self, bus):
        ch = FakeChannel({}, bus)
        await ch._handle_message("u1", "c1", "hello")
        msg = await bus.consume_inbound()
        assert msg.channel == "fake"
        assert msg.sender_id == "u1"
        assert msg.chat_id == "c1"
        assert msg.content == "hello"

    @pytest.mark.asyncio
    async def test_handle_message_new_command(self, bus):
        ch = FakeChannel({}, bus)
        await ch._handle_message("u1", "c1", "/new")
        assert ch._session_indices.get("u1") == 1
        assert len(ch.sent) == 1
        assert "已新建对话" in ch.sent[0].content
        assert bus.inbound_size == 0

    @pytest.mark.asyncio
    async def test_handle_message_help_command(self, bus):
        ch = FakeChannel({}, bus)
        await ch._handle_message("u1", "c1", "/help")
        assert len(ch.sent) == 1
        assert "/new" in ch.sent[0].content
        assert bus.inbound_size == 0

    @pytest.mark.asyncio
    async def test_handle_message_with_session_override(self, bus):
        ch = FakeChannel({}, bus)
        await ch._handle_message("u1", "c1", "/new")
        await ch._handle_message("u1", "c1", "hello")
        msg = await bus.consume_inbound()
        assert msg.content == "hello"
        assert msg.session_key_override == "fake:c1:session-1"

    @pytest.mark.asyncio
    async def test_handle_message_without_session_override(self, bus):
        ch = FakeChannel({}, bus)
        await ch._handle_message("u1", "c1", "hello")
        msg = await bus.consume_inbound()
        assert msg.content == "hello"
        assert msg.session_key_override is None

    @pytest.mark.asyncio
    async def test_handle_message_session_isolated_by_sender(self, bus):
        ch = FakeChannel({}, bus)
        await ch._handle_message("u1", "c1", "/new")
        await ch._handle_message("u2", "c1", "hi")
        msg = await bus.consume_inbound()
        assert msg.content == "hi"
        assert msg.session_key_override is None
