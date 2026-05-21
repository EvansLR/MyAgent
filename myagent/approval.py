"""Approval routing value objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApprovalRoute:
    """Where an approval request should be shown."""

    channel: str
    chat_id: str
