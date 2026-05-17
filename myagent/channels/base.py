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
        self._session_indices: dict[str, int] = {}

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
        """Wrap a platform event into an InboundMessage and publish to the bus.

        Intercepts ``/new`` and ``/help`` before they reach the agent loop.
        """
        text = content.strip()
        if text == "/new":
            self._session_indices[sender_id] = (
                self._session_indices.get(sender_id, 0) + 1
            )
            await self.send(
                OutboundMessage(
                    channel=self.name,
                    chat_id=chat_id,
                    content="已新建对话，历史记录已清空。",
                )
            )
            return
        if text == "/help":
            await self.send(
                OutboundMessage(
                    channel=self.name,
                    chat_id=chat_id,
                    content="可用命令：\n/new — 新建对话（清空当前历史记录）",
                )
            )
            return

        session_index = self._session_indices.get(sender_id, 0)
        session_key_override = None
        if session_index > 0:
            session_key_override = f"{self.name}:{chat_id}:session-{session_index}"

        await self.bus.publish_inbound(
            InboundMessage(
                channel=self.name,
                sender_id=str(sender_id),
                chat_id=str(chat_id),
                content=content,
                session_key_override=session_key_override,
            )
        )
