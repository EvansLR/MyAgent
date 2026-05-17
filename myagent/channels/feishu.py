"""Feishu (Lark) channel adapter using lark-oapi WebSocket + httpx."""

import asyncio
import html
import json
import os
import re
import threading
from uuid import uuid4

import httpx

from myagent.bus import OutboundMessage
from myagent.channels.base import BaseChannel


_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico", ".tiff", ".tif"}
_AUDIO_EXTS = {".opus"}
_VIDEO_EXTS = {".mp4", ".mov", ".avi"}
_FILE_TYPE_MAP = {
    ".opus": "opus",
    ".mp4": "mp4",
    ".pdf": "pdf",
    ".doc": "doc",
    ".docx": "doc",
    ".xls": "xls",
    ".xlsx": "xls",
    ".ppt": "ppt",
    ".pptx": "ppt",
}


def _event_to_text(event) -> str:
    """Extract plain text from a Feishu P2ImMessageReceiveV1 event.

    The callback receives a P2ImMessageReceiveV1 wrapper; the actual
    message data lives under ``event.event.message``.
    """
    try:
        raw = event.event.message.content
        content = json.loads(raw)
        return content.get("text", "")
    except Exception:
        return ""


def _event_to_card_action(event) -> tuple[str, bool] | None:
    """Extract an approval action from a Feishu card action event."""
    candidates = []
    for path in (
        ("event", "action", "value"),
        ("event", "event", "action", "value"),
        ("action", "value"),
    ):
        current = event
        try:
            for part in path:
                current = getattr(current, part)
            candidates.append(current)
        except Exception:
            continue
    for value in candidates:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                continue
        if not isinstance(value, dict):
            continue
        approval_id = str(value.get("approval_id") or "")
        action = str(value.get("action") or "").lower()
        if approval_id and action in {"approve", "deny"}:
            return approval_id, action == "approve"
    return None


class FeishuChannel(BaseChannel):
    """Receive and send Feishu messages via WebSocket long connection."""

    name = "feishu"

    def __init__(self, config: dict, bus) -> None:
        super().__init__(config, bus)
        self.app_id = str(config.get("appId") or config.get("app_id", ""))
        self.app_secret = str(
            config.get("appSecret") or config.get("app_secret", "")
        )
        self._token: str | None = None
        self._main_loop: asyncio.AbstractEventLoop | None = None
        self._ws_thread: threading.Thread | None = None
        self._lark_client: Any = None
        self._approval_futures: dict[str, asyncio.Future[bool]] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if not self.app_id or not self.app_secret:
            raise RuntimeError(
                "Feishu channel requires appId and appSecret in config"
            )
        self._running = True
        await self._refresh_token()
        self._main_loop = asyncio.get_running_loop()

        # Create lark client for file uploads
        import lark_oapi as lark

        self._lark_client = (
            lark.Client.builder()
            .app_id(self.app_id)
            .app_secret(self.app_secret)
            .log_level(lark.LogLevel.WARNING)
            .build()
        )

        self._ws_thread = threading.Thread(
            target=self._run_ws_sync, daemon=True
        )
        self._ws_thread.start()

    async def stop(self) -> None:
        self._running = False
        ws_thread = self._ws_thread
        self._ws_thread = None
        if ws_thread and ws_thread.is_alive():
            try:
                import lark_oapi.ws.client as ws_client

                ws_client.loop.call_soon_threadsafe(ws_client.loop.stop)
            except Exception:
                pass
            ws_thread.join(timeout=5)

    # ------------------------------------------------------------------
    # Outbound
    # ------------------------------------------------------------------

    async def send(self, msg: OutboundMessage) -> None:
        if msg.metadata.get("kind") == "approval_request":
            await self._send_approval_request(msg)
            return
        if not self._token:
            return
        receive_id_type = "chat_id" if msg.chat_id.startswith("oc_") else "open_id"

        # Send media files from explicit media list
        for file_path in msg.media:
            if not os.path.isfile(file_path):
                continue
            ext = os.path.splitext(file_path)[1].lower()
            if ext in _IMAGE_EXTS:
                key = await asyncio.to_thread(
                    self._upload_image_sync, file_path
                )
                if key:
                    await self._send_message(
                        receive_id_type,
                        msg.chat_id,
                        "image",
                        json.dumps({"image_key": key}),
                    )
            else:
                key = await asyncio.to_thread(
                    self._upload_file_sync, file_path
                )
                if key:
                    if ext in _AUDIO_EXTS:
                        media_type = "audio"
                    elif ext in _VIDEO_EXTS:
                        media_type = "video"
                    else:
                        media_type = "file"
                    await self._send_message(
                        receive_id_type,
                        msg.chat_id,
                        media_type,
                        json.dumps({"file_key": key}),
                    )

        # Send text content
        if msg.content and msg.content.strip():
            rendered = _render_text_message(msg.content.strip())
            await self._send_message(
                receive_id_type,
                msg.chat_id,
                rendered[0],
                json.dumps(rendered[1], ensure_ascii=False),
            )

    async def _send_approval_request(self, msg: OutboundMessage) -> None:
        future = msg.metadata.get("future")
        if not isinstance(future, asyncio.Future):
            return
        approval_id = uuid4().hex
        self._approval_futures[approval_id] = future
        if not self._token:
            return
        receive_id_type = "chat_id" if msg.chat_id.startswith("oc_") else "open_id"
        await self._send_message(
            receive_id_type,
            msg.chat_id,
            "interactive",
            json.dumps(_approval_card(approval_id, msg.content), ensure_ascii=False),
        )

    async def _send_message(
        self, receive_id_type: str, receive_id: str, msg_type: str, content: str
    ) -> None:
        url = (
            "https://open.feishu.cn/open-apis/im/v1/messages"
            f"?receive_id_type={receive_id_type}"
        )
        headers = {"Authorization": f"Bearer {self._token}"}
        payload = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": content,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
            except Exception:
                pass

    def _upload_image_sync(self, file_path: str) -> str | None:
        from lark_oapi.api.im.v1 import CreateImageRequest, CreateImageRequestBody
        try:
            with open(file_path, "rb") as f:
                request = (
                    CreateImageRequest.builder()
                    .request_body(
                        CreateImageRequestBody.builder()
                        .image_type("message")
                        .image(f)
                        .build()
                    )
                    .build()
                )
                response = self._lark_client.im.v1.image.create(request)
                if response.success():
                    return response.data.image_key
        except Exception:
            pass
        return None

    def _upload_file_sync(self, file_path: str) -> str | None:
        from lark_oapi.api.im.v1 import CreateFileRequest, CreateFileRequestBody
        ext = os.path.splitext(file_path)[1].lower()
        file_type = _FILE_TYPE_MAP.get(ext, "stream")
        file_name = os.path.basename(file_path)
        try:
            with open(file_path, "rb") as f:
                request = (
                    CreateFileRequest.builder()
                    .request_body(
                        CreateFileRequestBody.builder()
                        .file_type(file_type)
                        .file_name(file_name)
                        .file(f)
                        .build()
                    )
                    .build()
                )
                response = self._lark_client.im.v1.file.create(request)
                if response.success():
                    return response.data.file_key
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _refresh_token(self) -> None:
        url = (
            "https://open.feishu.cn/open-apis/auth/v3/"
            "tenant_access_token/internal"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                json={
                    "app_id": self.app_id,
                    "app_secret": self.app_secret,
                },
            )
            data = resp.json()
            self._token = data.get("tenant_access_token")

    def _run_ws_sync(self) -> None:
        """Run the lark-oapi WS client in a dedicated thread with its own loop."""
        import lark_oapi.ws.client as ws_client
        from lark_oapi import EventDispatcherHandler
        from lark_oapi.ws import Client as WSClient

        # Replace the module-level loop so client.start() doesn't clash
        # with the main thread's running event loop.
        new_loop = asyncio.new_event_loop()
        ws_client.loop = new_loop
        asyncio.set_event_loop(new_loop)

        builder = EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(
            self._on_message
        )
        if hasattr(builder, "register_p2_card_action_trigger"):
            builder = builder.register_p2_card_action_trigger(self._on_card_action)
        handler = builder.build()

        client = WSClient(
            self.app_id,
            self.app_secret,
            event_handler=handler,
            auto_reconnect=True,
        )
        client.start()

    def _on_message(self, event) -> None:
        """Callback invoked by lark-oapi when a message arrives.

        This runs inside the WSClient's thread, so we ship the async
        work back to the main event loop via run_coroutine_threadsafe.
        """
        try:
            text = _event_to_text(event)
            if not text:
                return
            sender = ""
            chat_id = ""
            try:
                sender = event.event.sender.sender_id.open_id
                chat_id = event.event.message.chat_id or sender
            except Exception:
                pass
            target_loop = self._main_loop
            if target_loop and target_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._handle_message(sender, chat_id, text),
                    target_loop,
                )
            else:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._handle_message(sender, chat_id, text))
                except RuntimeError:
                    pass
        except Exception:
            pass

    def _on_card_action(self, event) -> None:
        """Resolve a pending approval from a Feishu card button click."""
        action = _event_to_card_action(event)
        if action is None:
            return
        approval_id, approved = action
        future = self._approval_futures.pop(approval_id, None)
        if future is None or future.done():
            return
        target_loop = self._main_loop
        if target_loop and target_loop.is_running():
            target_loop.call_soon_threadsafe(future.set_result, approved)
        else:
            future.set_result(approved)


def _approval_card(approval_id: str, prompt: str) -> dict:
    """Build a minimal Feishu interactive card for one approval request."""
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "orange",
            "title": {"tag": "plain_text", "content": "MyAgent 权限审批"},
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"需要你确认后才能继续执行：\n\n```text\n{_card_escape(prompt)}\n```",
                },
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "允许"},
                        "type": "primary",
                        "value": {"approval_id": approval_id, "action": "approve"},
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "拒绝"},
                        "type": "danger",
                        "value": {"approval_id": approval_id, "action": "deny"},
                    },
                ],
            },
        ],
    }


def _card_escape(text: str) -> str:
    """Keep prompt text compact inside a card code block."""
    compact = text.strip()
    if len(compact) > 1800:
        compact = compact[:1800] + "\n... (truncated)"
    return compact.replace("```", "'''")


def _render_text_message(text: str) -> tuple[str, dict]:
    """Render plain/markdown-ish text as Feishu text or post message content."""
    if _should_send_plain_text(text):
        return "text", {"text": text}
    return "post", {
        "zh_cn": {
            "title": "",
            "content": _markdown_to_post_content(text),
        }
    }


def _should_send_plain_text(text: str) -> bool:
    if len(text) > 500:
        return False
    markdown_markers = ("```", "\n#", "\n-", "\n*", "\n1.", "**", "__", "[")
    return not any(marker in text for marker in markdown_markers)


def _markdown_to_post_content(text: str) -> list[list[dict]]:
    """Convert a small Markdown subset to Feishu post rich-text paragraphs."""
    rows: list[list[dict]] = []
    in_code = False
    code_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code:
                rows.append([_text_tag("\n".join(code_lines), un_escape=True)])
                code_lines = []
                in_code = False
            else:
                if code_lines:
                    code_lines = []
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not stripped:
            rows.append([_text_tag(" ")])
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            rows.append([_text_tag(heading.group(2), bold=True)])
            continue
        bullet = re.match(r"^[-*]\s+(.+)$", stripped)
        if bullet:
            rows.append([_text_tag("- "), *_inline_tags(bullet.group(1))])
            continue
        numbered = re.match(r"^(\d+[.)])\s+(.+)$", stripped)
        if numbered:
            rows.append([_text_tag(f"{numbered.group(1)} "), *_inline_tags(numbered.group(2))])
            continue
        rows.append(_inline_tags(stripped))
    if in_code and code_lines:
        rows.append([_text_tag("\n".join(code_lines), un_escape=True)])
    return rows or [[_text_tag(text)]]


def _inline_tags(text: str) -> list[dict]:
    """Render links and bold markers for Feishu post content."""
    tags: list[dict] = []
    position = 0
    pattern = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)|\*\*([^*]+)\*\*|__([^_]+)__")
    for match in pattern.finditer(text):
        if match.start() > position:
            tags.append(_text_tag(text[position:match.start()]))
        if match.group(1) and match.group(2):
            tags.append({
                "tag": "a",
                "text": match.group(1),
                "href": match.group(2),
            })
        else:
            tags.append(_text_tag(match.group(3) or match.group(4) or "", bold=True))
        position = match.end()
    if position < len(text):
        tags.append(_text_tag(text[position:]))
    return tags or [_text_tag("")]


def _text_tag(text: str, *, bold: bool = False, un_escape: bool = False) -> dict:
    tag = {"tag": "text", "text": text}
    if bold:
        tag["style"] = ["bold"]
    if un_escape:
        tag["un_escape"] = True
        tag["text"] = html.escape(text)
    return tag
