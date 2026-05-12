"""Event types passed through the message bus."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class InboundMessage:
    """Message received from a user-facing channel."""

    channel: str
    sender_id: str
    chat_id: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    session_key_override: str | None = None

    @property
    def session_key(self) -> str:
        """Return the stable session key used by the runtime."""
        return self.session_key_override or f"{self.channel}:{self.chat_id}"


@dataclass(slots=True)
class OutboundMessage:
    """Message sent from the agent runtime back to a channel."""

    channel: str
    chat_id: str
    content: str
    reply_to: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    media: list[str] = field(default_factory=list)
