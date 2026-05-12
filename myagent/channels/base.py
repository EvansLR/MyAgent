"""Abstract base for chat channel adapters."""

from abc import ABC, abstractmethod

from myagent.bus import InboundMessage, MessageBus, OutboundMessage


class BaseChannel(ABC):
    """Each channel (Feishu, QQ, etc.) implements this interface
    to integrate with the agent message bus.
    """

    name: str = "base"

    def __init__(self, config: dict, bus: MessageBus) -> None:
        self.config = config
        self.bus = bus
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    async def start(self) -> None:
        """Open the platform connection and begin receiving events."""
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        """Drain and close the platform connection."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Outbound
    # ------------------------------------------------------------------

    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """Deliver an agent reply to the platform."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Inbound helper
    # ------------------------------------------------------------------

    async def _handle_message(
        self,
        sender_id: str,
        chat_id: str,
        content: str,
    ) -> None:
        """Wrap a platform event into an InboundMessage and publish to the bus."""
        await self.bus.publish_inbound(
            InboundMessage(
                channel=self.name,
                sender_id=str(sender_id),
                chat_id=str(chat_id),
                content=content,
            )
        )
