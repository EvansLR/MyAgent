"""Tests for cron JSON persistence."""

import json
from pathlib import Path

import pytest

from myagent.cron.store import CronStore
from myagent.cron.types import CronJob, CronPayload, CronRunRecord, CronSchedule


@pytest.fixture
def tmp_store(tmp_path: Path) -> CronStore:
    return CronStore(tmp_path / "cron" / "jobs.json")


def test_load_empty(tmp_store: CronStore) -> None:
    jobs = tmp_store.load()
    assert jobs == []


def test_round_trip(tmp_store: CronStore) -> None:
    job = CronJob(
        id="abc123",
        name="test",
        enabled=True,
        schedule=CronSchedule(kind="every", every=60),
        payload=CronPayload(message="hello"),
        created_at=1000.0,
        updated_at=2000.0,
    )
    tmp_store.save([job])

    loaded = tmp_store.load()
    assert len(loaded) == 1
    assert loaded[0].id == "abc123"
    assert loaded[0].schedule.kind == "every"
    assert loaded[0].schedule.every == 60
    assert loaded[0].payload.message == "hello"


def test_run_history_round_trip(tmp_store: CronStore) -> None:
    job = CronJob(
        id="j1",
        name="history-test",
        schedule=CronSchedule(kind="at", at=1234567890.0),
        state=CronJobState(
            run_history=[
                CronRunRecord(run_at=1000.0, status="ok", duration_ms=50),
                CronRunRecord(run_at=2000.0, status="error", duration_ms=30, error="boom"),
            ]
        ),
    )
    tmp_store.save([job])
    loaded = tmp_store.load()[0]
    assert len(loaded.state.run_history) == 2
    assert loaded.state.run_history[0].status == "ok"
    assert loaded.state.run_history[1].error == "boom"


def test_corrupt_file_preserved(tmp_store: CronStore, tmp_path: Path) -> None:
    tmp_store.path.parent.mkdir(parents=True, exist_ok=True)
    tmp_store.path.write_text("not json", encoding="utf-8")

    with pytest.raises(RuntimeError) as exc_info:
        tmp_store.load()
    assert "corrupt" in str(exc_info.value)
    assert "preserved" in str(exc_info.value)

    # Original file should have been renamed
    assert not tmp_store.path.exists()
    corrupt_files = list(tmp_store.path.parent.glob("*.corrupt-*"))
    assert len(corrupt_files) == 1


def test_atomic_write(tmp_store: CronStore) -> None:
    job = CronJob(id="x", name="y", schedule=CronSchedule(kind="every", every=1))
    tmp_store.save([job])
    assert tmp_store.path.exists()
    # No temp file left behind
    assert list(tmp_store.path.parent.glob("*.tmp")) == []


def test_from_dict_to_dict_symmetry(tmp_store: CronStore) -> None:
    job = CronJob(
        id="sym",
        name="symmetry",
        enabled=False,
        schedule=CronSchedule(kind="at", at=999.0),
        payload=CronPayload(message="msg"),
        delete_after_run=True,
    )
    tmp_store.save([job])
    raw = json.loads(tmp_store.path.read_text(encoding="utf-8"))
    assert raw["jobs"][0]["id"] == "sym"
    assert raw["jobs"][0]["delete_after_run"] is True


from myagent.cron.types import CronJobState
