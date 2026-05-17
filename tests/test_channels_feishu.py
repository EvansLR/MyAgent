"""Tests for FeishuChannel."""

import json
from unittest.mock import MagicMock, patch

import pytest

from myagent.bus import MessageBus, OutboundMessage
from myagent.channels.feishu import (
    FeishuChannel,
    _approval_card,
    _event_to_card_action,
    _event_to_text,
    _markdown_to_post_content,
    _render_text_message,
)


class TestEventToText:
    def test_plain_text(self):
        event = MagicMock()
        event.event.message.content = '{"text":"hello"}'
        assert _event_to_text(event) == "hello"

    def test_bad_json(self):
        event = MagicMock()
        event.event.message.content = "not json"
        assert _event_to_text(event) == ""


class TestCardAction:
    def test_extract_card_approval_action(self):
        event = MagicMock()
        event.event.action.value = {"approval_id": "a1", "action": "approve"}
        assert _event_to_card_action(event) == ("a1", True)

    def test_extract_card_deny_action_from_json(self):
        event = MagicMock()
        event.event.action.value = '{"approval_id":"a1","action":"deny"}'
        assert _event_to_card_action(event) == ("a1", False)

    def test_approval_card_contains_buttons(self):
        card = _approval_card("a1", "Execute shell command:\necho hi")
        assert card["header"]["title"]["content"] == "MyAgent 权限审批"
        actions = card["elements"][1]["actions"]
        assert actions[0]["text"]["content"] == "允许"
        assert actions[0]["value"] == {"approval_id": "a1", "action": "approve"}
        assert actions[1]["text"]["content"] == "拒绝"
        assert actions[1]["value"] == {"approval_id": "a1", "action": "deny"}


class TestFeishuRendering:
    def test_short_plain_text_stays_text(self):
        msg_type, content = _render_text_message("hello")
        assert msg_type == "text"
        assert content == {"text": "hello"}

    def test_markdown_renders_as_post(self):
        msg_type, content = _render_text_message("# Title\n\n- **bold** item\n")
        assert msg_type == "post"
        rows = content["zh_cn"]["content"]
        assert rows[0][0]["text"] == "Title"
        assert rows[0][0]["style"] == ["bold"]
        assert rows[2][0]["text"] == "- "
        assert rows[2][1]["text"] == "bold"
        assert rows[2][1]["style"] == ["bold"]

    def test_links_render_as_anchor_tags(self):
        rows = _markdown_to_post_content("see [docs](https://example.com)")
        assert rows[0][1] == {
            "tag": "a",
            "text": "docs",
            "href": "https://example.com",
        }

    def test_code_block_renders_as_text_block(self):
        rows = _markdown_to_post_content("```powershell\nGet-Process\n```")
        assert rows[0][0]["tag"] == "text"
        assert "Get-Process" in rows[0][0]["text"]
        assert rows[0][0]["un_escape"] is True


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
    async def test_send_approval_request_stores_future_without_token(self, channel):
        future = asyncio.get_running_loop().create_future()
        await channel.send(
            OutboundMessage(
                channel="feishu",
                chat_id="c1",
                content="Approve me",
                metadata={"kind": "approval_request", "future": future},
            )
        )
        assert len(channel._approval_futures) == 1

    @pytest.mark.asyncio
    async def test_send_approval_request_uses_interactive_card(self, channel):
        future = asyncio.get_running_loop().create_future()
        channel._token = "token"
        sent = []

        async def fake_send_message(receive_id_type, receive_id, msg_type, content):
            sent.append((receive_id_type, receive_id, msg_type, json.loads(content)))

        channel._send_message = fake_send_message
        await channel.send(
            OutboundMessage(
                channel="feishu",
                chat_id="oc_123",
                content="Approve command",
                metadata={"kind": "approval_request", "future": future},
            )
        )

        assert sent[0][0] == "chat_id"
        assert sent[0][2] == "interactive"
        assert sent[0][3]["header"]["title"]["content"] == "MyAgent 权限审批"

    @pytest.mark.asyncio
    async def test_send_markdown_uses_post_message(self, channel):
        channel._token = "token"
        sent = []

        async def fake_send_message(receive_id_type, receive_id, msg_type, content):
            sent.append((receive_id_type, receive_id, msg_type, json.loads(content)))

        channel._send_message = fake_send_message
        await channel.send(
            OutboundMessage(
                channel="feishu",
                chat_id="oc_123",
                content="# Title\n\n- item",
            )
        )

        assert sent[0][2] == "post"
        assert sent[0][3]["zh_cn"]["content"][0][0]["text"] == "Title"

    def test_card_action_resolves_pending_future(self, channel):
        loop = asyncio.new_event_loop()
        try:
            future = loop.create_future()
            channel._approval_futures["a1"] = future
            event = MagicMock()
            event.event.action.value = {"approval_id": "a1", "action": "approve"}

            channel._on_card_action(event)

            assert future.result() is True
            assert "a1" not in channel._approval_futures
        finally:
            loop.close()

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
