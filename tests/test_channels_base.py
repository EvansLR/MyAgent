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
