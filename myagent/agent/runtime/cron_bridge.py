"""Cron job bridge for AgentLoop."""

from __future__ import annotations

from myagent.bus import InboundMessage, MessageBus
from myagent.cron.types import CronJob, CronSchedule
from myagent.memory import MemoryConsolidator


class AgentCronBridge:
    """Connect cron jobs to memory maintenance and inbound agent messages."""

    def __init__(
        self,
        bus: MessageBus,
        memory_consolidator: MemoryConsolidator,
    ) -> None:
        self.bus = bus
        self.memory_consolidator = memory_consolidator

    def register_memory_consolidation_job(self, cron_service) -> None:
        """Register the periodic memory consolidation system job."""
        for job in cron_service.list_jobs(include_disabled=True):
            if job.name == "memory_consolidation" and job.payload.job_type == "system":
                return
        cron_service.add_job(
            name="memory_consolidation",
            schedule=CronSchedule(kind="every", every=24 * 3600),
            message="consolidate memory",
            channel="",
            chat_id="",
            delete_after_run=False,
            job_type="system",
        )

    async def on_job(self, job: CronJob) -> None:
        """Handle one cron job firing."""
        if job.payload.job_type == "system":
            if job.name == "memory_consolidation":
                try:
                    await self.memory_consolidator.consolidate()
                except Exception:
                    pass
            return
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
