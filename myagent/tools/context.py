"""Explicit runtime context passed to tools during one agent turn."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable

from myagent.approval import ApprovalRoute


ApprovalCallback = Callable[[str, ApprovalRoute], Awaitable[bool]]


@dataclass(slots=True)
class ToolExecutionContext:
    """Per-turn context for tools that need runtime services."""

    session_key: str
    turn_id: str
    channel: str
    chat_id: str
    approval_callback: ApprovalCallback | None = None
    attachments: list[str] = field(default_factory=list)

    @property
    def approval_route(self) -> ApprovalRoute:
        return ApprovalRoute(self.channel, self.chat_id)

    async def request_approval(self, prompt: str) -> bool:
        if self.approval_callback is None:
            return False
        return await self.approval_callback(prompt, self.approval_route)
