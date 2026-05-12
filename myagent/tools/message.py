"""Message tool for sending messages (with optional files) to users."""

from typing import Any, Awaitable, Callable

from myagent.bus import OutboundMessage
from myagent.tools.base import Tool


class MessageTool(Tool):
    """Tool to send messages to users on chat channels.

    Agent can call this explicitly when it needs to send files or
    intermediate progress updates. If used in a turn, the final
    auto-generated reply is suppressed to avoid duplication.
    """

    def __init__(
        self,
        send_callback: Callable[[OutboundMessage], Awaitable[None]] | None = None,
    ) -> None:
        self._send_callback = send_callback
        self._default_channel: str = ""
        self._default_chat_id: str = ""
        self._sent_in_turn: bool = False

    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the current message context."""
        self._default_channel = channel
        self._default_chat_id = chat_id

    def start_turn(self) -> None:
        """Reset per-turn send tracking."""
        self._sent_in_turn = False

    @property
    def name(self) -> str:
        return "message"

    @property
    def description(self) -> str:
        return (
            "Send a message (and optional files) to the user. "
            "Use this when you need to send files, images, or intermediate updates. "
            "If you use this tool, the final auto-reply is suppressed to avoid duplication."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The message text to send",
                },
                "media": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Optional list of local file paths to attach "
                        "(images, documents, audio, video)"
                    ),
                },
            },
            "required": ["content"],
        }

    async def execute(
        self,
        content: str,
        media: list[str] | None = None,
        **kwargs: Any,
    ) -> str:
        if not self._send_callback:
            return "Error: Message sending not configured"

        msg = OutboundMessage(
            channel=self._default_channel,
            chat_id=self._default_chat_id,
            content=content,
            media=media or [],
        )
        await self._send_callback(msg)
        self._sent_in_turn = True
        media_info = f" with {len(media or [])} attachments" if media else ""
        return f"Message sent{media_info}"
