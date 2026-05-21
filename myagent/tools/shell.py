"""Shell command execution tool with safety guardrails."""

import asyncio
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from myagent.tools.base import Tool
from myagent.tools.context import (
    ApprovalCallback,
    ToolExecutionContext,
    call_approval_callback,
)
from myagent.tools.shell_risk import ShellRisk, classify_shell_command


def _decode_bytes(data: bytes) -> str:
    """Decode subprocess output trying common encodings."""
    for encoding in ("utf-8", "gbk", "gb2312", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")

class ShellCommandTool(Tool):
    """Execute a shell command with safety guardrails."""

    def __init__(
        self,
        workspace: Path | str | None = None,
        approval_callback: ApprovalCallback | None = None,
    ) -> None:
        self.workspace = Path(workspace or ".").resolve()
        self.cwd = self.workspace
        self.approval_callback = approval_callback

    @property
    def name(self) -> str:
        return "execute_command"

    @property
    def description(self) -> str:
        return (
            "Execute a shell command on the local computer. "
            "Use for reading system info, running build scripts, checking logs, etc. "
            "On Windows, commands run with PowerShell semantics; use "
            "Invoke-WebRequest -Uri <url> -OutFile <path> for downloads. "
            "The cd command changes this tool's working directory for later calls. "
            "Readonly queries, version checks, and safe read-only pipelines run automatically. "
            "Destructive or complex commands require user approval."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Maximum seconds to wait for the command.",
                    "minimum": 1,
                    "maximum": 300,
                },
            },
            "required": ["command"],
        }

    async def execute(
        self,
        command: str,
        timeout: int = 30,
        _context: ToolExecutionContext | None = None,
        **_: Any,
    ) -> str:
        command = command.strip()
        if not command:
            return "Error: Empty command."

        cd_target = self._cd_target(command)
        if cd_target is not None:
            return await self._change_directory(cd_target)

        risk = classify_shell_command(command)
        if risk == ShellRisk.DENY:
            return "Error: Command denied by safety policy."
        if risk == ShellRisk.CONFIRM:
            if _context is None and self.approval_callback is None:
                return (
                    "Error: This command requires user approval, "
                    "but no approval callback is configured."
                )
            prompt = f"Execute shell command:\n{command}"
            approved = (
                await _context.request_approval(prompt)
                if _context is not None
                else await call_approval_callback(self.approval_callback, prompt, None)
            )
            if not approved:
                return "Error: User denied command execution."

        return await self._run(command, timeout)

    async def _run(self, command: str, timeout: int) -> str:
        is_windows = platform.system() == "Windows"
        try:
            if is_windows:
                proc = await asyncio.create_subprocess_exec(
                    *_windows_shell_command(command),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=self.cwd,
                )
            else:
                shell = os.environ.get("SHELL", "/bin/sh")
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=self.cwd,
                    executable=shell,
                )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2)
            except asyncio.TimeoutError:
                pass
            return f"Error: Command timed out after {timeout} seconds."
        except Exception as exc:
            return f"Error: {exc}"

        try:
            await asyncio.wait_for(proc.wait(), timeout=2)
        except asyncio.TimeoutError:
            pass

        out_text = _decode_bytes(stdout)
        err_text = _decode_bytes(stderr)

        parts: list[str] = []
        if out_text:
            parts.append(out_text)
        if err_text:
            parts.append(f"[stderr]\n{err_text}")

        output = "\n\n".join(parts)
        if not output.strip():
            return (
                f"Command completed with exit code {proc.returncode} "
                f"in {self.cwd} (no output)."
            )

        if len(output) > 8000:
            output = output[:8000] + f"\n\n... (truncated, total {len(output)} chars)"

        return f"Exit code: {proc.returncode}\nWorking directory: {self.cwd}\n\n{output}"

    def _cd_target(self, command: str) -> str | None:
        """Return a target path for simple cd commands, or None for normal commands."""
        text = command.strip()
        lowered = text.lower()
        if lowered in {"cd", "pwd"}:
            return ""
        match = re.match(r"^(cd|chdir|pushd|set-location|sl)\s+(.+)$", text, re.IGNORECASE)
        if not match:
            return None
        target = match.group(2).strip()
        if target.lower().startswith("/d "):
            target = target[3:].strip()
        return _strip_quotes(target)

    async def _change_directory(self, target: str) -> str:
        """Persist a working-directory change across tool calls."""
        if not target:
            return f"Current directory: {self.cwd}"
        path = Path(os.path.expanduser(os.path.expandvars(target)))
        if not path.is_absolute():
            path = self.cwd / path
        try:
            resolved = path.resolve()
        except OSError as exc:
            return f"Error: Cannot resolve directory '{target}': {exc}"
        if not resolved.exists():
            return f"Error: Directory does not exist: {resolved}"
        if not resolved.is_dir():
            return f"Error: Not a directory: {resolved}"
        self.cwd = resolved
        return f"Current directory: {self.cwd}"


def _strip_quotes(text: str) -> str:
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def _windows_shell_command(command: str) -> list[str]:
    """Build a PowerShell command line for Windows terminal semantics."""
    shell = shutil.which("pwsh") or shutil.which("powershell") or "powershell.exe"
    prelude = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "$OutputEncoding = [System.Text.Encoding]::UTF8; "
    )
    return [
        shell,
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        prelude + command,
    ]
