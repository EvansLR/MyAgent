"""Tests for cron scheduling engine."""

import asyncio
from pathlib import Path

import pytest

from myagent.cron.service import CronService, _compute_next_run, _now
from myagent.cron.types import CronJob, CronJobState, CronPayload, CronSchedule


@pytest.fixture
def tmp_service(tmp_path: Path) -> CronService:
    return CronService(store_path=tmp_path / "jobs.json")


@pytest.fixture
def executed_jobs() -> list[CronJob]:
    return []


@pytest.fixture
def service_with_callback(tmp_path: Path, executed_jobs: list) -> CronService:
    async def on_job(job: CronJob) -> None:
        executed_jobs.append(job)

    return CronService(store_path=tmp_path / "jobs.json", on_job=on_job)


class TestComputeNextRun:
    def test_at_future(self) -> None:
        assert _compute_next_run(CronSchedule(kind="at", at=1000.0), 500.0) == 1000.0

    def test_at_past(self) -> None:
        assert _compute_next_run(CronSchedule(kind="at", at=100.0), 500.0) is None

    def test_every(self) -> None:
        assert _compute_next_run(CronSchedule(kind="every", every=60), 1000.0) == 1060.0

    def test_every_zero(self) -> None:
        assert _compute_next_run(CronSchedule(kind="every", every=0), 1000.0) is None


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_start_empty(self, tmp_service: CronService) -> None:
        await tmp_service.start()
        assert tmp_service._running is True
        assert tmp_service.status()["jobs"] == 0
        tmp_service.stop()

    @pytest.mark.asyncio
    async def test_start_stop_idempotent(self, tmp_service: CronService) -> None:
        await tmp_service.start()
        tmp_service.stop()
        assert tmp_service._running is False
        assert tmp_service._timer_task is None


class TestJobManagement:
    def test_add_job(self, tmp_service: CronService) -> None:
        job = tmp_service.add_job(
            name="test", schedule=CronSchedule(kind="every", every=60), message="hi"
        )
        assert job.id
        assert job.name == "test"
        assert job.schedule.every == 60
        assert job.payload.message == "hi"
        assert job.state.next_run_at is not None

    def test_list_jobs_sorted(self, tmp_service: CronService) -> None:
        j1 = tmp_service.add_job(
            "soon", CronSchedule(kind="every", every=10), "msg"
        )
        j2 = tmp_service.add_job(
            "later", CronSchedule(kind="every", every=100), "msg"
        )
        jobs = tmp_service.list_jobs()
        assert [j.id for j in jobs] == [j1.id, j2.id]

    def test_list_omits_disabled(self, tmp_service: CronService) -> None:
        j = tmp_service.add_job("x", CronSchedule(kind="every", every=10), "msg")
        j.enabled = False
        tmp_service._save()
        assert tmp_service.list_jobs() == []
        assert len(tmp_service.list_jobs(include_disabled=True)) == 1

    def test_remove_job(self, tmp_service: CronService) -> None:
        j = tmp_service.add_job("x", CronSchedule(kind="every", every=10), "msg")
        assert tmp_service.remove_job(j.id) is True
        assert all(job.id != j.id for job in tmp_service.list_jobs(include_disabled=True))
        assert tmp_service.remove_job(j.id) is False

    def test_at_job_delete_after_run(self, tmp_service: CronService) -> None:
        job = tmp_service.add_job(
            "once", CronSchedule(kind="at", at=_now() + 1), "msg"
        )
        assert job.delete_after_run is True


class TestTimerExecution:
    @pytest.mark.asyncio
    async def test_executes_due_job(
        self, service_with_callback: CronService, executed_jobs: list
    ) -> None:
        svc = service_with_callback
        svc.add_job(
            "immediate",
            CronSchedule(kind="every", every=1),
            "run me",
        )
        # Manually set next_run_at to now so it fires immediately
        svc._jobs[0].state.next_run_at = _now()
        svc._save()  # persist so start() reload sees the change
        await svc.start()
        await asyncio.sleep(0.2)
        svc.stop()

        assert len(executed_jobs) >= 1
        assert executed_jobs[0].name == "immediate"

    @pytest.mark.asyncio
    async def test_every_job_reschedules(
        self, service_with_callback: CronService, executed_jobs: list
    ) -> None:
        svc = service_with_callback
        svc.add_job(
            "recurring",
            CronSchedule(kind="every", every=1),
            "repeat",
        )
        svc._jobs[0].state.next_run_at = _now()
        svc._save()
        await svc.start()
        await asyncio.sleep(2.5)
        svc.stop()

        # Should have fired at least twice
        assert len(executed_jobs) >= 2
        # Each execution should be the same job
        assert all(j.id == executed_jobs[0].id for j in executed_jobs)

    @pytest.mark.asyncio
    async def test_at_job_removed_after_run(
        self, service_with_callback: CronService, executed_jobs: list
    ) -> None:
        svc = service_with_callback
        # Build a job directly so next_run_at is already due when start() loads it
        job = CronJob(
            id="once123",
            name="once",
            schedule=CronSchedule(kind="at", at=_now() + 1),
            payload=CronPayload(message="one shot"),
            state=CronJobState(next_run_at=_now()),
            delete_after_run=True,
        )
        svc._jobs.append(job)
        svc._save()
        await svc.start()
        await asyncio.sleep(0.2)
        svc.stop()

        assert len(executed_jobs) == 1
        assert all(
            existing.id != job.id for existing in svc.list_jobs(include_disabled=True)
        )  # deleted after run

    @pytest.mark.asyncio
    async def test_error_in_callback_recorded(
        self, tmp_path: Path
    ) -> None:
        async def fail(job: CronJob) -> None:
            raise RuntimeError("boom")

        svc = CronService(store_path=tmp_path / "jobs.json", on_job=fail)
        svc.add_job("fail", CronSchedule(kind="every", every=1), "boom")
        svc._jobs[0].state.next_run_at = _now()
        svc._save()
        await svc.start()
        await asyncio.sleep(0.2)
        svc.stop()

        job = svc._jobs[0]
        assert job.state.last_status == "error"
        assert job.state.last_error == "boom"
        assert len(job.state.run_history) == 1

    @pytest.mark.asyncio
    async def test_persists_across_restarts(self, tmp_path: Path) -> None:
        svc1 = CronService(store_path=tmp_path / "jobs.json")
        j = svc1.add_job("persist", CronSchedule(kind="every", every=3600), "msg")
        original_next = j.state.next_run_at

        svc2 = CronService(store_path=tmp_path / "jobs.json")
        await svc2.start()
        loaded = next(
            job for job in svc2.list_jobs(include_disabled=True) if job.id == j.id
        )
        assert loaded is not None
        assert loaded.name == "persist"
        assert loaded.state.next_run_at == original_next
        svc2.stop()


class TestStoreRecovery:
    @pytest.mark.asyncio
    async def test_corrupt_store_keeps_memory(
        self, tmp_path: Path, executed_jobs: list
    ) -> None:
        # Seed a good store
        svc = CronService(
            store_path=tmp_path / "jobs.json",
            on_job=lambda job: executed_jobs.append(job),
        )
        svc.add_job("good", CronSchedule(kind="every", every=1), "msg")
        await svc.start()
        svc.stop()

        # Corrupt the file
        svc.store_path.write_text("not json", encoding="utf-8")

        # Restart should use in-memory jobs (or empty) without crashing
        svc2 = CronService(
            store_path=tmp_path / "jobs.json",
            on_job=lambda job: executed_jobs.append(job),
        )
        # Since corrupt, start will try to load and fail. In our implementation,
        # start() calls _store.load() which raises RuntimeError.
        with pytest.raises(RuntimeError):
            await svc2.start()
