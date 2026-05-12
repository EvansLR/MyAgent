"""Channel lifecycle manager."""

import asyncio

from myagent.bus import MessageBus
from myagent.channels.base import BaseChannel


class ChannelManager:
    """Owns and coordinates all enabled channel adapters."""

    def __init__(self, bus: MessageBus | None = None) -> None:
        self._bus = bus
        self._channels: dict[str, BaseChannel] = {}
        self._dispatch_task: asyncio.Task | None = None

    def register(self, channel: BaseChannel) -> None:
        """Add one channel adapter."""
        self._channels[channel.name] = channel

    @property
    def channels(self) -> dict[str, BaseChannel]:
        return dict(self._channels)

    async def start_all(self) -> None:
        """Start every registered channel and the outbound dispatcher."""
        if not self._channels:
            return

        # Start outbound dispatcher first so replies are never lost.
        if self._bus is not None:
            self._dispatch_task = asyncio.create_task(self._dispatch_outbound())

        results = await asyncio.gather(
            *[c.start() for c in self._channels.values()],
            return_exceptions=True,
        )
        for name, result in zip(self._channels.keys(), results):
            if isinstance(result, Exception):
                print(f"[ChannelManager] {name} channel failed to start: {result}")

    async def stop_all(self) -> None:
        """Stop every registered channel and the dispatcher."""
        if self._dispatch_task is not None:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass
            self._dispatch_task = None

        if self._channels:
            await asyncio.gather(
                *[c.stop() for c in self._channels.values()],
                return_exceptions=True,
            )

    async def _dispatch_outbound(self) -> None:
        """Consume outbound messages from the bus and route to channels."""
        if self._bus is None:
            return
        while True:
            try:
                msg = await asyncio.wait_for(
                    self._bus.consume_outbound(), timeout=1.0
                )
                channel = self._channels.get(msg.channel)
                # Fallback: if no exact channel match, send to the first
                # registered channel (handles legacy cron jobs with
                # channel="scheduler" and jobs without a saved channel).
                if channel is None and self._channels:
                    channel = next(iter(self._channels.values()))
                if channel is not None:
                    try:
                        await channel.send(msg)
                    except Exception:
                        pass
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
