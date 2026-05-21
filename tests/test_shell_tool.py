"""Tests for ShellCommandTool."""

import platform
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from myagent.tools.context import ToolExecutionContext
from myagent.tools.shell import ShellCommandTool
from myagent.tools.shell_risk import ShellRisk, classify_shell_command


@pytest.fixture
def tool():
    return ShellCommandTool(workspace=Path(".").resolve())


def make_context(approval_callback):
    return ToolExecutionContext(
        session_key="test:default",
        turn_id="turn-1",
        channel="cli",
        chat_id="default",
        approval_callback=approval_callback,
    )


class TestShellCommandTool:
    @pytest.mark.asyncio
    async def test_name(self, tool):
        assert tool.name == "execute_command"

    @pytest.mark.asyncio
    async def test_safe_command_executes_without_approval(self, tool):
        result = await tool.execute("echo hello")
        assert "hello" in result
        assert "Exit code: 0" in result

    @pytest.mark.asyncio
    async def test_dangerous_prefix_requires_approval(self, tool):
        approve = AsyncMock(return_value=True)
        result = await tool.execute("rm file.txt", _context=make_context(approve))
        approve.assert_awaited_once()
        assert "Exit code:" in result or "Error:" in result

    @pytest.mark.asyncio
    async def test_version_probe_executes_without_approval(self, tool):
        result = await tool.execute("cmake --version")
        assert "requires user approval" not in result

    @pytest.mark.asyncio
    async def test_operator_requires_approval(self, tool):
        approve = AsyncMock(return_value=True)
        result = await tool.execute("echo hello && echo world", _context=make_context(approve))
        approve.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unsafe_pipe_requires_approval(self, tool):
        approve = AsyncMock(return_value=False)
        result = await tool.execute("echo hello | Out-File result.txt", _context=make_context(approve))
        approve.assert_awaited_once()
        assert "User denied" in result

    @pytest.mark.asyncio
    async def test_safe_pipe_executes_without_approval(self, tool):
        if platform.system() == "Windows":
            command = "Get-Process | Measure-Object | Select-Object -ExpandProperty Count"
        else:
            command = "echo hello | grep hello"

        result = await tool.execute(command)

        assert "requires user approval" not in result
        assert "Exit code: 0" in result

    @pytest.mark.asyncio
    async def test_no_callback_returns_error(self, tool):
        result = await tool.execute("unknown-build-tool --list")
        assert "requires user approval" in result
        assert "tool execution context" in result

    @pytest.mark.asyncio
    async def test_user_denied_returns_error(self, tool):
        approve = AsyncMock(return_value=False)
        result = await tool.execute("unknown-build-tool --list", _context=make_context(approve))
        assert "User denied" in result

    @pytest.mark.asyncio
    async def test_empty_command(self, tool):
        result = await tool.execute("")
        assert "Empty command" in result

    @pytest.mark.asyncio
    async def test_timeout(self, tool):
        approve = AsyncMock(return_value=True)
        result = await tool.execute(
            "python -c \"import time; time.sleep(5)\"",
            timeout=0.1,
            _context=make_context(approve),
        )
        assert "timed out" in result

    @pytest.mark.asyncio
    async def test_output_truncation(self, tool):
        approve = AsyncMock(return_value=True)
        result = await tool.execute(
            "python -c \"print('x' * 10000)\"",
            _context=make_context(approve),
        )
        assert "truncated" in result
        assert len(result) <= 8200

    @pytest.mark.asyncio
    async def test_stderr_included(self, tool):
        approve = AsyncMock(return_value=True)
        result = await tool.execute(
            "python -c \"import sys; sys.stderr.write('error msg')\"",
            _context=make_context(approve),
        )
        assert "[stderr]" in result
        assert "error msg" in result

    @pytest.mark.asyncio
    async def test_cd_is_safe(self, tool):
        result = await tool.execute("cd .")
        assert "Current directory:" in result

    @pytest.mark.asyncio
    async def test_cd_persists_working_directory(self, tmp_path: Path):
        workspace = tmp_path / "workspace"
        subdir = workspace / "subdir"
        subdir.mkdir(parents=True)
        (subdir / "note.txt").write_text("hello", encoding="utf-8")
        tool = ShellCommandTool(workspace=workspace)

        cd_result = await tool.execute("cd subdir")
        list_result = await tool.execute("dir" if platform.system() == "Windows" else "ls")

        assert str(subdir.resolve()) in cd_result
        assert "note.txt" in list_result

    @pytest.mark.asyncio
    async def test_cd_missing_directory_returns_error(self, tool):
        result = await tool.execute("cd does-not-exist")
        assert "Directory does not exist" in result

    @pytest.mark.asyncio
    async def test_windows_powershell_info_command_is_safe(self, tool):
        if platform.system() != "Windows":
            pytest.skip("Windows-only shell command")
        result = await tool.execute("Get-CimInstance Win32_Battery")
        assert "requires user approval" not in result

    @pytest.mark.asyncio
    async def test_windows_powershell_expression_query_is_safe(self, tool):
        if platform.system() != "Windows":
            pytest.skip("Windows-only shell command")
        result = await tool.execute("(Get-Process).Count")
        assert "requires user approval" not in result

    @pytest.mark.parametrize(
        ("command", "risk"),
        [
            ("git status --short", ShellRisk.ALLOW),
            ("git log --oneline -5", ShellRisk.ALLOW),
            ("git commit -m change", ShellRisk.CONFIRM),
            ("python --version", ShellRisk.ALLOW),
            ("python -m pytest tests/test_shell_tool.py", ShellRisk.ALLOW),
            ("python -c \"print('hi')\"", ShellRisk.CONFIRM),
            ("Get-ChildItem | Select-String note", ShellRisk.ALLOW),
            ("Get-Process | Measure-Object | Select-Object Count", ShellRisk.ALLOW),
            ("echo hello | Out-File result.txt", ShellRisk.CONFIRM),
            ("echo hello && echo world", ShellRisk.CONFIRM),
            ("unknown-build-tool --list", ShellRisk.CONFIRM),
        ],
    )
    def test_shell_risk_classification(self, command, risk):
        assert classify_shell_command(command) == risk

    @pytest.mark.asyncio
    async def test_parameters_schema(self, tool):
        schema = tool.parameters
        assert schema["type"] == "object"
        assert "command" in schema["properties"]
        assert "timeout" in schema["properties"]
        assert schema["required"] == ["command"]
