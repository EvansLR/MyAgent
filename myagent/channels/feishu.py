"""Feishu (Lark) channel adapter using lark-oapi WebSocket + httpx."""

import asyncio
import json
import os
import threading
import time
from typing import Any
from uuid import uuid4

import httpx

from myagent.bus import OutboundMessage
from myagent.channels.base import BaseChannel
from myagent.channels.feishu_rendering import (
    _approval_card,
    _inline_tags,
    _markdown_to_post_content,
    _render_text_message,
    _should_send_plain_text,
    _text_tag,
)


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
_TOKEN_REFRESH_MARGIN_SECONDS = 300
_WS_RECONNECT_DELAY_SECONDS = 5
_FEISHU_TOKEN_ERROR_CODES = {99991663, 99991664, 99991665}


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
        self._token_expires_at: float = 0
        self._main_loop: asyncio.AbstractEventLoop | None = None
        self._ws_thread: threading.Thread | None = None
        self._lark_client: Any = None
        self._approval_futures: dict[str, asyncio.Future[bool]] = {}
        self._ws_connected = False
        self._last_event_at: float = 0
        self._last_ws_error: str = ""

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
        if not await self._ensure_token():
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
        if not await self._ensure_token():
            if not future.done():
                future.set_result(False)
            return
        approval_id = uuid4().hex
        self._approval_futures[approval_id] = future
        receive_id_type = "chat_id" if msg.chat_id.startswith("oc_") else "open_id"
        sent = await self._send_message(
            receive_id_type,
            msg.chat_id,
            "interactive",
            json.dumps(_approval_card(approval_id, msg.content), ensure_ascii=False),
        )
        if sent is False:
            self._approval_futures.pop(approval_id, None)
            if not future.done():
                future.set_result(False)

    async def _send_message(
        self, receive_id_type: str, receive_id: str, msg_type: str, content: str
    ) -> bool:
        if not await self._ensure_token():
            return False
        return await self._send_message_with_retry(
            receive_id_type, receive_id, msg_type, content
        )

    async def _send_message_with_retry(
        self, receive_id_type: str, receive_id: str, msg_type: str, content: str
    ) -> bool:
        ok, should_refresh = await self._post_message(
            receive_id_type, receive_id, msg_type, content
        )
        if ok or not should_refresh:
            return ok
        print("[FeishuChannel] tenant_access_token may be expired; refreshing and retrying send.")
        await self._refresh_token()
        ok, _ = await self._post_message(receive_id_type, receive_id, msg_type, content)
        return ok

    async def _post_message(
        self, receive_id_type: str, receive_id: str, msg_type: str, content: str
    ) -> tuple[bool, bool]:
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
            except Exception as exc:
                print(f"[FeishuChannel] Failed to send {msg_type} message: {exc}")
                return False, False

        should_refresh = resp.status_code in {401, 403}
        try:
            data = resp.json()
        except Exception:
            data = {}
        code = data.get("code") if isinstance(data, dict) else None
        if code in _FEISHU_TOKEN_ERROR_CODES:
            should_refresh = True
        if resp.status_code >= 400 or (isinstance(code, int) and code != 0):
            print(
                "[FeishuChannel] Feishu send failed: "
                f"status={resp.status_code}, code={code}, body={resp.text[:500]}"
            )
            return False, should_refresh
        return True, False

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
            expire = int(data.get("expire") or 7200)
            self._token_expires_at = time.time() + expire

    async def _ensure_token(self) -> bool:
        if not self.app_id or not self.app_secret:
            return False
        if self._token and self._token_expires_at == 0:
            return True
        if self._token and time.time() < self._token_expires_at - _TOKEN_REFRESH_MARGIN_SECONDS:
            return True
        try:
            await self._refresh_token()
        except Exception as exc:
            print(f"[FeishuChannel] Failed to refresh tenant_access_token: {exc}")
            return bool(self._token)
        return bool(self._token)

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

        try:
            while self._running:
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
                self._ws_connected = True
                try:
                    print("[FeishuChannel] WebSocket client starting.")
                    client.start()
                    if self._running:
                        self._last_ws_error = "WebSocket client returned unexpectedly."
                        print(f"[FeishuChannel] {self._last_ws_error}")
                except Exception as exc:
                    self._last_ws_error = str(exc)
                    print(f"[FeishuChannel] WebSocket error: {exc}")
                finally:
                    self._ws_connected = False

                if self._running:
                    time.sleep(_WS_RECONNECT_DELAY_SECONDS)
        finally:
            try:
                new_loop.close()
            except Exception:
                pass

    def _on_message(self, event) -> None:
        """Callback invoked by lark-oapi when a message arrives.

        This runs inside the WSClient's thread, so we ship the async
        work back to the main event loop via run_coroutine_threadsafe.
        """
        try:
            text = _event_to_text(event)
            if not text:
                return
            self._last_event_at = time.time()
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
