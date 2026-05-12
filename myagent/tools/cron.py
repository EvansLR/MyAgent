"""Cron tool for scheduling reminders and tasks."""

from datetime import datetime
from typing import Any

from myagent.cron.service import CronService
from myagent.cron.types import CronSchedule
from myagent.tools.base import Tool


class CronTool(Tool):
    """Tool to schedule reminders and recurring tasks."""

    def __init__(self, cron_service: CronService) -> None:
        self._cron = cron_service

    @property
    def name(self) -> str:
        return "cron"

    @property
    def description(self) -> str:
        return (
            "Schedule reminders and tasks. Actions: add, list, remove. "
            "Use every_seconds for recurring intervals (e.g. 'every 5 minutes'). "
            "Use every_seconds + once=true for one-shot delayed reminders (e.g. 'in 30 seconds'). "
            "Use at for exact future timestamps (e.g. 'tomorrow at 9am')."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "remove"],
                    "description": "Action to perform",
                },
                "message": {
                    "type": "string",
                    "description": (
                        "Instruction for the agent to execute when the job triggers. "
                        "Required for add."
                    ),
                },
                "every_seconds": {
                    "type": "integer",
                    "description": (
                        "Interval in seconds for recurring tasks (e.g. 300 for 5 minutes). "
                        "Required for add if not using at."
                    ),
                    "minimum": 1,
                },
                "at": {
                    "type": "string",
                    "description": (
                        "ISO datetime for one-time execution (e.g. '2026-05-11T14:00:00'). "
                        "Required for add if not using every_seconds."
                    ),
                },
                "once": {
                    "type": "boolean",
                    "description": (
                        "If true, run only once and then delete. "
                        "Use for one-shot reminders like 'in 5 minutes' or 'after 30 seconds'. "
                        "Ignored when using 'at'."
                    ),
                },
                "job_id": {
                    "type": "string",
                    "description": "Job ID to remove. Required for remove.",
                },
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        message: str = "",
        every_seconds: int | None = None,
        at: str | None = None,
        once: bool = False,
        job_id: str | None = None,
        _channel: str = "",
        _chat_id: str = "",
        **kwargs: Any,
    ) -> str:
        if action == "add":
            return self._add_job(message, every_seconds, at, once, _channel, _chat_id)
        if action == "list":
            return self._list_jobs()
        if action == "remove":
            return self._remove_job(job_id)
        return f"Unknown action: {action}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_job(
        self,
        message: str,
        every_seconds: int | None,
        at: str | None,
        once: bool = False,
        channel: str = "",
        chat_id: str = "",
    ) -> str:
        if not message or not message.strip():
            return (
                "Error: cron action='add' requires a non-empty 'message' parameter "
                "describing what to do when the job triggers."
            )

        if every_seconds is not None:
            schedule = CronSchedule(kind="every", every=every_seconds)
        elif at:
            try:
                dt = datetime.fromisoformat(at)
            except ValueError:
                return f"Error: invalid ISO datetime format '{at}'. Expected: YYYY-MM-DDTHH:MM:SS"
            ts = dt.timestamp()
            from time import time as _now
            if ts <= _now():
                return (
                    f"Error: the specified time '{at}' is in the past or present. "
                    f"Please provide a future time or use every_seconds for relative reminders."
                )
            schedule = CronSchedule(kind="at", at=ts)
        else:
            return "Error: either every_seconds or at is required for add"

        job = self._cron.add_job(
            name=message[:30],
            schedule=schedule,
            message=message,
            channel=channel,
            chat_id=chat_id,
            delete_after_run=once,
        )
        timing = "once" if once else ("at" if at else "recurring")
        return f"Created {timing} job '{job.name}' (id: {job.id})"

    def _list_jobs(self) -> str:
        jobs = self._cron.list_jobs()
        if not jobs:
            return "No scheduled jobs."
        lines: list[str] = []
        for j in jobs:
            timing = self._format_timing(j.schedule, j.state.next_run_at)
            parts = [f"- {j.name} (id: {j.id}, {timing})"]
            if j.state.last_run_at:
                parts.append(
                    f"  last run: {j.state.last_status} at "
                    f"{datetime.fromtimestamp(j.state.last_run_at).isoformat()}"
                )
            lines.append("\n".join(parts))
        return "Scheduled jobs:\n" + "\n".join(lines)

    def _remove_job(self, job_id: str | None) -> str:
        if not job_id:
            return "Error: job_id is required for remove"
        if self._cron.remove_job(job_id):
            return f"Removed job {job_id}"
        return f"Job {job_id} not found"

    @staticmethod
    def _format_timing(
        schedule: CronSchedule, next_run: float | None
    ) -> str:
        if schedule.kind == "every" and schedule.every:
            if schedule.every % 3600 == 0:
                return f"every {schedule.every // 3600}h"
            if schedule.every % 60 == 0:
                return f"every {schedule.every // 60}m"
            return f"every {schedule.every}s"
        if schedule.kind == "at" and next_run:
            return f"at {datetime.fromtimestamp(next_run).isoformat()}"
        return schedule.kind
