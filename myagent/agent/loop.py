"""Minimal agent loop for processing messages from the bus."""

import asyncio

from myagent.bus import InboundMessage, MessageBus, OutboundMessage
from myagent.agent.context import ContextBuilder, Message
from myagent.providers import BaseProvider, create_provider


class AgentLoop:
    """Consume inbound messages, ask a provider, and publish outbound replies."""

    def __init__(
        self,
        bus: MessageBus,
        provider: BaseProvider | None = None,
        context_builder: ContextBuilder | None = None,
    ) -> None:
        self.bus = bus
        self.provider = provider or create_provider()
        self.context_builder = context_builder or ContextBuilder()
        self._history: dict[str, list[Message]] = {}
        self._lock = asyncio.Lock()
        self._running = False

    @property
    def running(self) -> bool:
        """Return whether the loop should keep processing messages."""
        return self._running

    @property
    def locked(self) -> bool:
        """Return whether a turn is currently being processed."""
        return self._lock.locked()

    async def process_next(self) -> OutboundMessage:
        """Process one inbound message and publish one outbound message."""
        inbound = await self.bus.consume_inbound()
        async with self._lock:
            return await self.process_message(inbound)

    async def process_message(self, inbound: InboundMessage) -> OutboundMessage:
        """Generate and publish an outbound response for one inbound message."""
        history = self._history_for(inbound.session_key)
        messages = self.context_builder.build_messages(inbound, history)
        content = await self.provider.generate(messages)
        outbound = OutboundMessage(
            channel=inbound.channel,
            chat_id=inbound.chat_id,
            content=content,
        )
        await self.bus.publish_outbound(outbound)
        history.extend(
            [
                {"role": "user", "content": inbound.content},
                {"role": "assistant", "content": content},
            ]
        )
        return outbound

    async def run_until_stopped(self) -> None:
        """Keep processing messages until stopped or cancelled."""
        self._running = True
        while self._running:
            await self.process_next()

    def stop(self) -> None:
        """Request the processing loop to stop."""
        self._running = False

    def history_for(self, session_key: str) -> list[Message]:
        """Return a copy of the current session history."""
        return list(self._history_for(session_key))

    def _history_for(self, session_key: str) -> list[Message]:
        return self._history.setdefault(session_key, [])
