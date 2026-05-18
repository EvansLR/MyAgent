"""Async in-memory message bus."""

import asyncio

from myagent.bus.events import InboundMessage, OutboundMessage


class MessageBus:
    """Two-queue bus that decouples channels from the agent loop."""

    def __init__(self) -> None:
        self._inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self._outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()

    async def publish_inbound(self, msg: InboundMessage) -> None:
        """Publish a channel message for the agent loop."""
        await self._inbound.put(msg)

    async def consume_inbound(self) -> InboundMessage:
        """Wait for and return the next inbound message."""
        return await self._inbound.get()

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """Publish an agent response for a channel."""
        await self._outbound.put(msg)

    async def consume_outbound(self) -> OutboundMessage:
        """Wait for and return the next outbound message."""
        return await self._outbound.get()
