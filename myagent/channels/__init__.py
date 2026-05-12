"""Channel adapters for chat platforms."""

from myagent.channels.base import BaseChannel
from myagent.channels.feishu import FeishuChannel
from myagent.channels.manager import ChannelManager

__all__ = [
    "BaseChannel",
    "ChannelManager",
    "FeishuChannel",
]
