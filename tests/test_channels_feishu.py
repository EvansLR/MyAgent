"""Tests for FeishuChannel."""

import json
from unittest.mock import MagicMock, patch

import pytest

from myagent.bus import MessageBus, OutboundMessage
from myagent.channels.feishu import FeishuChannel, _event_to_text


class TestEventToText:
    def test_plain_text(self):
        event = MagicMock()
        event.event.message.content = '{"text":"hello"}'
        assert _event_to_text(event) == "hello"

    def test_bad_json(self):
        event = MagicMock()
        event.event.message.content = "not json"
        assert _event_to_text(event) == ""


class TestFeishuChannel:
    @pytest.fixture
    def bus(self):
        return MessageBus()

    @pytest.fixture
    def channel(self, bus):
        return FeishuChannel(
            {"appId": "test_id", "appSecret": "test_secret"}, bus
        )

    def test_init_reads_config(self, channel):
        assert channel.app_id == "test_id"
        assert channel.app_secret == "test_secret"

    def test_name(self, channel):
        assert channel.name == "feishu"

    @pytest.mark.asyncio
    async def test_start_without_credentials_raises(self, bus):
        ch = FeishuChannel({}, bus)
        with pytest.raises(RuntimeError):
            await ch.start()

    @pytest.mark.asyncio
    async def test_send_without_token(self, channel):
        # Should not crash when token is missing
        await channel.send(OutboundMessage(
            channel="feishu", chat_id="u1", content="hi"
        ))

    @pytest.mark.asyncio
    async def test_on_message_publishes_inbound(self, channel, bus):
        event = MagicMock()
        event.event.message.content = '{"text":"hi"}'
        event.event.sender.sender_id.open_id = "u1"
        event.event.message.chat_id = "c1"

        channel._on_message(event)

        # The callback schedules a task; give the loop a tick
        await asyncio.sleep(0)

        msg = await bus.consume_inbound()
        assert msg.content == "hi"
        assert msg.sender_id == "u1"
        assert msg.chat_id == "c1"

    @pytest.mark.asyncio
    async def test_feishu_new_command(self, bus):
        channel = FeishuChannel(
            {"appId": "test", "appSecret": "test"}, bus
        )
        await channel._handle_message("u1", "c1", "/new")
        assert channel._session_indices.get("u1") == 1
        assert bus.inbound_size == 0

    @pytest.mark.asyncio
    async def test_feishu_session_override(self, bus):
        channel = FeishuChannel(
            {"appId": "test", "appSecret": "test"}, bus
        )
        await channel._handle_message("u1", "c1", "/new")
        await channel._handle_message("u1", "c1", "hello")
        msg = await bus.consume_inbound()
        assert msg.session_key_override == "feishu:c1:session-1"


import asyncio
