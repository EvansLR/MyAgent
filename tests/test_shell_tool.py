"""Tests for ShellCommandTool."""

import platform
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from myagent.tools.shell import ShellCommandTool


@pytest.fixture
def tool():
    return ShellCommandTool(workspace=Path(".").resolve())


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
        tool.approval_callback = AsyncMock(return_value=True)
        result = await tool.execute("rm file.txt")
        tool.approval_callback.assert_awaited_once()
        assert "Exit code:" in result or "Error:" in result

    @pytest.mark.asyncio
    async def test_unknown_command_requires_approval(self, tool):
        tool.approval_callback = AsyncMock(return_value=True)
        result = await tool.execute("cmake --version")
        tool.approval_callback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_operator_requires_approval(self, tool):
        tool.approval_callback = AsyncMock(return_value=True)
        result = await tool.execute("echo hello && echo world")
        tool.approval_callback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unsafe_pipe_requires_approval(self, tool):
        tool.approval_callback = AsyncMock(return_value=False)
        result = await tool.execute("echo hello | Out-File result.txt")
        tool.approval_callback.assert_awaited_once()
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
        result = await tool.execute("cmake --version")
        assert "requires user approval" in result

    @pytest.mark.asyncio
    async def test_user_denied_returns_error(self, tool):
        tool.approval_callback = AsyncMock(return_value=False)
        result = await tool.execute("cmake --version")
        assert "User denied" in result

    @pytest.mark.asyncio
    async def test_empty_command(self, tool):
        result = await tool.execute("")
        assert "Empty command" in result

    @pytest.mark.asyncio
    async def test_timeout(self, tool):
        tool.approval_callback = AsyncMock(return_value=True)
        result = await tool.execute(
            "python -c \"import time; time.sleep(5)\"", timeout=0.1
        )
        assert "timed out" in result

    @pytest.mark.asyncio
    async def test_output_truncation(self, tool):
        tool.approval_callback = AsyncMock(return_value=True)
        result = await tool.execute(
            "python -c \"print('x' * 10000)\""
        )
        assert "truncated" in result
        assert len(result) <= 8200

    @pytest.mark.asyncio
    async def test_stderr_included(self, tool):
        tool.approval_callback = AsyncMock(return_value=True)
        result = await tool.execute(
            "python -c \"import sys; sys.stderr.write('error msg')\""
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

    @pytest.mark.asyncio
    async def test_parameters_schema(self, tool):
        schema = tool.parameters
        assert schema["type"] == "object"
        assert "command" in schema["properties"]
        assert "timeout" in schema["properties"]
        assert schema["required"] == ["command"]
