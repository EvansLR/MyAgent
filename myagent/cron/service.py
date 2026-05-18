"""Cron service for scheduling agent tasks."""

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

from myagent.cron.store import CronStore
from myagent.cron.types import (
    CronJob,
    CronJobState,
    CronPayload,
    CronRunRecord,
    CronSchedule,
)

DEFAULT_MAX_SLEEP_S = 300  # 5 minutes
_MAX_RUN_HISTORY = 20


def _now() -> float:
    return time.time()


def _compute_next_run(schedule: CronSchedule, now: float) -> float | None:
    """Compute next run time as a Unix timestamp."""
    if schedule.kind == "at":
        return schedule.at if schedule.at and schedule.at > now else None
    if schedule.kind == "every":
        if not schedule.every or schedule.every <= 0:
            return None
        return now + schedule.every
    return None


class CronService:
    """Service for managing and executing scheduled jobs."""

    def __init__(
        self,
        store_path: Path,
        on_job: Callable[[CronJob], Awaitable[None]] | None = None,
        max_sleep_s: int = DEFAULT_MAX_SLEEP_S,
    ) -> None:
        self.store_path = store_path
        self.on_job = on_job
        self.max_sleep_s = max_sleep_s
        self._store = CronStore(store_path)
        self._jobs: list[CronJob] = []
        self._timer_task: asyncio.Task | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the cron service."""
        self._running = True
        self._jobs = self._store.load()
        self._recompute_next_runs()
        self._save()
        self._arm_timer()

    def stop(self) -> None:
        """Stop the cron service."""
        self._running = False
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None

    # ------------------------------------------------------------------
    # Timer loop
    # ------------------------------------------------------------------

    def _recompute_next_runs(self) -> None:
        """Recompute next run times for all enabled jobs."""
        now = _now()
        for job in self._jobs:
            if job.enabled and job.state.next_run_at is None:
                job.state.next_run_at = _compute_next_run(job.schedule, now)

    def _get_next_wake(self) -> float | None:
        """Get the earliest next run time across all enabled jobs."""
        times = [
            j.state.next_run_at
            for j in self._jobs
            if j.enabled and j.state.next_run_at is not None
        ]
        return min(times) if times else None

    def _arm_timer(self) -> None:
        """Schedule the next timer tick."""
        if self._timer_task:
            self._timer_task.cancel()

        if not self._running:
            return

        next_wake = self._get_next_wake()
        if next_wake is None:
            delay = self.max_sleep_s
        else:
            delay = min(self.max_sleep_s, max(0.0, next_wake - _now()))

        async def tick() -> None:
            await asyncio.sleep(delay)
            if self._running:
                await self._on_timer()

        self._timer_task = asyncio.create_task(tick())

    async def _on_timer(self) -> None:
        """Handle timer tick — run due jobs."""
        try:
            self._jobs = self._store.load()
        except RuntimeError:
            # Corrupt store on disk; keep using in-memory snapshot.
            pass

        now = _now()
        due_jobs = [
            j
            for j in self._jobs
            if j.enabled
            and j.state.next_run_at is not None
            and now >= j.state.next_run_at
        ]

        for job in due_jobs:
            await self._execute_job(job)

        self._save()
        self._arm_timer()

    async def _execute_job(self, job: CronJob) -> None:
        """Execute a single job."""
        start = _now()
        try:
            if self.on_job:
                await self.on_job(job)
            job.state.last_status = "ok"
            job.state.last_error = None
        except Exception as exc:
            job.state.last_status = "error"
            job.state.last_error = str(exc)

        end = _now()
        job.state.last_run_at = start
        job.state.updated_at = end

        job.state.run_history.append(
            CronRunRecord(
                run_at=start,
                status=job.state.last_status or "unknown",
                duration_ms=int((end - start) * 1000),
                error=job.state.last_error,
            )
        )
        job.state.run_history = job.state.run_history[-_MAX_RUN_HISTORY:]

        # Handle one-shot vs recurring
        if job.delete_after_run:
            self._jobs = [j for j in self._jobs if j.id != job.id]
        elif job.schedule.kind == "at":
            job.enabled = False
            job.state.next_run_at = None
        else:
            job.state.next_run_at = _compute_next_run(job.schedule, _now())

    def _save(self) -> None:
        """Save jobs to disk."""
        self._store.save(self._jobs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_jobs(self, include_disabled: bool = False) -> list[CronJob]:
        """List all jobs sorted by next run time."""
        jobs = self._jobs if include_disabled else [j for j in self._jobs if j.enabled]
        return sorted(jobs, key=lambda j: j.state.next_run_at or float("inf"))

    def add_job(
        self,
        name: str,
        schedule: CronSchedule,
        message: str,
        channel: str = "",
        chat_id: str = "",
        delete_after_run: bool | None = None,
        job_type: str = "user",
    ) -> CronJob:
        """Add a new job."""
        now = _now()
        if delete_after_run is None:
            delete_after_run = schedule.kind == "at"
        job = CronJob(
            id=str(uuid.uuid4())[:8],
            name=name,
            enabled=True,
            schedule=schedule,
            payload=CronPayload(message=message, channel=channel, chat_id=chat_id, job_type=job_type),
            state=CronJobState(next_run_at=_compute_next_run(schedule, now)),
            created_at=now,
            updated_at=now,
            delete_after_run=delete_after_run,
        )
        self._jobs.append(job)
        self._save()
        self._arm_timer()
        return job

    def remove_job(self, job_id: str) -> bool:
        """Remove a job by ID."""
        before = len(self._jobs)
        self._jobs = [j for j in self._jobs if j.id != job_id]
        removed = len(self._jobs) < before
        if removed:
            self._save()
            self._arm_timer()
        return removed

    def status(self) -> dict:
        """Get service status."""
        return {
            "running": self._running,
            "jobs": len(self._jobs),
            "next_wake_at": self._get_next_wake(),
        }
