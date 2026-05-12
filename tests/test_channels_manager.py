"""Tests for ChannelManager."""

import pytest

from myagent.bus import MessageBus, OutboundMessage
from myagent.channels.base import BaseChannel
from myagent.channels.manager import ChannelManager


class DummyChannel(BaseChannel):
    _counter = 0

    def __init__(self, config, bus):
        super().__init__(config, bus)
        DummyChannel._counter += 1
        self.name = f"dummy{DummyChannel._counter}"
        self.started = False
        self.stopped = False

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def send(self, msg):
        pass


@pytest.fixture
def bus():
    return MessageBus()


class TestChannelManager:
    def test_register(self, bus):
        mgr = ChannelManager()
        ch = DummyChannel({}, bus)
        mgr.register(ch)
        assert len(mgr.channels) == 1

    @pytest.mark.asyncio
    async def test_start_all(self, bus):
        mgr = ChannelManager()
        ch1 = DummyChannel({}, bus)
        ch2 = DummyChannel({}, bus)
        mgr.register(ch1)
        mgr.register(ch2)
        await mgr.start_all()
        assert ch1.started
        assert ch2.started

    @pytest.mark.asyncio
    async def test_stop_all(self, bus):
        mgr = ChannelManager()
        ch = DummyChannel({}, bus)
        mgr.register(ch)
        await mgr.start_all()
        await mgr.stop_all()
        assert ch.stopped

    @pytest.mark.asyncio
    async def test_empty_manager(self, bus):
        mgr = ChannelManager()
        await mgr.start_all()
        await mgr.stop_all()
