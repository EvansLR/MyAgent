"""Cron job bridge for AgentLoop."""

from __future__ import annotations

from myagent.bus import InboundMessage, MessageBus
from myagent.cron.types import CronJob


class AgentCronBridge:
    """Connect cron jobs to inbound agent messages."""

    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus

    async def on_job(self, job: CronJob) -> None:
        """Handle one cron job firing."""
        await self.bus.publish_inbound(self._message_for_user_job(job))

    def _message_for_user_job(self, job: CronJob) -> InboundMessage:
        channel = job.payload.channel or "scheduler"
        chat_id = job.payload.chat_id or job.id
        content = (
            f"[Scheduled task triggered] Task name: {job.name}\n"
            "This is a reminder the user previously scheduled, and it is now due.\n"
            f"Reminder content: {job.payload.message}\n\n"
            "Execute the reminder directly and generate a message for the user. "
            "Do not ask the user scheduling questions, and do not create another "
            "scheduled task."
        )
        return InboundMessage(
            channel=channel,
            sender_id="cron",
            chat_id=chat_id,
            content=content,
            metadata={"job_name": job.name, "source": "cron"},
            session_key_override=f"cron:{job.id}",
        )
