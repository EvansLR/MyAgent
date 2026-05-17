"""Turn-local approval routing context."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApprovalRoute:
    """Where an approval request should be shown."""

    channel: str
    chat_id: str


_CURRENT_APPROVAL_ROUTE: ContextVar[ApprovalRoute | None] = ContextVar(
    "myagent_current_approval_route",
    default=None,
)


def set_current_approval_route(route: ApprovalRoute | None):
    """Set the current approval route and return a reset token."""
    return _CURRENT_APPROVAL_ROUTE.set(route)


def reset_current_approval_route(token) -> None:
    """Reset the current approval route to a previous token."""
    _CURRENT_APPROVAL_ROUTE.reset(token)


def current_approval_route() -> ApprovalRoute | None:
    """Return the current turn-local approval route."""
    return _CURRENT_APPROVAL_ROUTE.get()
