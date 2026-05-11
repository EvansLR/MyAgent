"""Tests for the agent-facing cron tool."""

from pathlib import Path

import pytest

from myagent.cron.service import CronService
from myagent.tools.cron import CronTool


@pytest.fixture
def cron_tool(tmp_path: Path) -> CronTool:
    svc = CronService(store_path=tmp_path / "jobs.json")
    return CronTool(svc)


class TestAdd:
    @pytest.mark.asyncio
    async def test_add_every(self, cron_tool: CronTool) -> None:
        result = await cron_tool.execute(
            action="add", message="drink water", every_seconds=1200
        )
        assert "Created job" in result
        assert "drink water" in result

    @pytest.mark.asyncio
    async def test_add_at(self, cron_tool: CronTool) -> None:
        result = await cron_tool.execute(
            action="add", message="meeting", at="2099-01-01T10:00:00"
        )
        assert "Created job" in result
        assert "meeting" in result

    @pytest.mark.asyncio
    async def test_add_missing_message(self, cron_tool: CronTool) -> None:
        result = await cron_tool.execute(action="add", every_seconds=60)
        assert "Error" in result
        assert "message" in result.lower()

    @pytest.mark.asyncio
    async def test_add_missing_schedule(self, cron_tool: CronTool) -> None:
        result = await cron_tool.execute(action="add", message="test")
        assert "Error" in result
        assert "every_seconds or at" in result

    @pytest.mark.asyncio
    async def test_add_invalid_at(self, cron_tool: CronTool) -> None:
        result = await cron_tool.execute(
            action="add", message="test", at="not-a-date"
        )
        assert "Error" in result
        assert "invalid ISO datetime" in result


class TestList:
    @pytest.mark.asyncio
    async def test_list_empty(self, cron_tool: CronTool) -> None:
        result = await cron_tool.execute(action="list")
        assert "No scheduled jobs" in result

    @pytest.mark.asyncio
    async def test_list_with_jobs(self, cron_tool: CronTool) -> None:
        await cron_tool.execute(action="add", message="j1", every_seconds=60)
        await cron_tool.execute(action="add", message="j2", every_seconds=3600)
        result = await cron_tool.execute(action="list")
        assert "j1" in result
        assert "j2" in result
        assert "every 1m" in result or "every 60s" in result
        assert "every 1h" in result


class TestRemove:
    @pytest.mark.asyncio
    async def test_remove_success(self, cron_tool: CronTool) -> None:
        add_result = await cron_tool.execute(
            action="add", message="temp", every_seconds=60
        )
        job_id = add_result.split("id: ")[1].rstrip(")")
        result = await cron_tool.execute(action="remove", job_id=job_id)
        assert "Removed" in result

    @pytest.mark.asyncio
    async def test_remove_not_found(self, cron_tool: CronTool) -> None:
        result = await cron_tool.execute(action="remove", job_id="nope")
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_remove_missing_id(self, cron_tool: CronTool) -> None:
        result = await cron_tool.execute(action="remove")
        assert "Error" in result


class TestUnknownAction:
    @pytest.mark.asyncio
    async def test_unknown(self, cron_tool: CronTool) -> None:
        result = await cron_tool.execute(action="magic")
        assert "Unknown action" in result
