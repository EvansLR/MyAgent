"""Explicit runtime context passed to tools during one agent turn."""

from __future__ import annotations

from dataclasses import dataclass, field
import inspect
from typing import Awaitable, Callable

from myagent.approval import ApprovalRoute


ApprovalCallback = Callable[..., Awaitable[bool]]


async def call_approval_callback(
    callback: ApprovalCallback,
    prompt: str,
    route: ApprovalRoute | None,
) -> bool:
    """Call old prompt-only or new prompt+route approval callbacks."""
    signature = inspect.signature(callback)
    accepts_varargs = any(
        parameter.kind == inspect.Parameter.VAR_POSITIONAL
        for parameter in signature.parameters.values()
    )
    positional_count = sum(
        1
        for parameter in signature.parameters.values()
        if parameter.kind
        in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        }
    )
    if accepts_varargs or positional_count >= 2:
        return await callback(prompt, route)
    return await callback(prompt)


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
        return await call_approval_callback(
            self.approval_callback,
            prompt,
            self.approval_route,
        )
