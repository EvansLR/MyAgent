"""Shell command execution tool with safety guardrails."""

import asyncio
import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Awaitable, Callable

from myagent.tools.base import Tool


ApprovalCallback = Callable[[str], Awaitable[bool]]


def _decode_bytes(data: bytes) -> str:
    """Decode subprocess output trying common encodings."""
    for encoding in ("utf-8", "gbk", "gb2312", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")

# Characters/operators that indicate command chaining or redirection.
_DANGEROUS_OPERATORS = (";", "&&", "||", "|", ">", "<", "`", "$(", "${")

# Command prefixes that are inherently dangerous
_DANGEROUS_PREFIXES = frozenset({
    "rm", "del", "format", "mkfs", "dd", "chmod", "chown",
    "sudo", "su",
})

# Command prefixes considered safe/readonly
_SAFE_PREFIXES = frozenset({
    "echo", "cat", "ls", "dir", "pwd", "cd", "whoami", "hostname",
    "date", "uname", "df", "du", "ps", "top", "env", "which", "where",
    "find", "grep", "head", "tail", "wc", "type",
    # System info
    "wmic", "powercfg", "systeminfo", "ver", "winver",
    "pmset", "system_profiler", "sw_vers", "sysctl",
    "acpi", "upower", "lshw", "lspci", "lsusb", "dmidecode",
    # Version / readonly tools
    "python", "python3", "node", "go", "rustc", "cargo",
    "java", "javac", "dotnet", "gcc", "g++", "clang",
    # Git readonly
    "git",
    # Package managers readonly
    "pip", "pip3",
})


class ShellCommandTool(Tool):
    """Execute a shell command with safety guardrails."""

    def __init__(
        self,
        workspace: Path | str | None = None,
        approval_callback: ApprovalCallback | None = None,
    ) -> None:
        self.workspace = Path(workspace or ".").resolve()
        self.approval_callback = approval_callback

    @property
    def name(self) -> str:
        return "execute_command"

    @property
    def description(self) -> str:
        return (
            "Execute a shell command on the local computer. "
            "Use for reading system info, running build scripts, checking logs, etc. "
            "Readonly commands (ls, cat, echo, etc.) run automatically. "
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

    async def execute(self, command: str, timeout: int = 30, **_: Any) -> str:
        command = command.strip()
        if not command:
            return "Error: Empty command."

        if self._needs_approval(command):
            if self.approval_callback is None:
                return (
                    "Error: This command requires user approval, "
                    "but no approval callback is configured."
                )
            approved = await self.approval_callback(
                f"Execute shell command:\n{command}"
            )
            if not approved:
                return "Error: User denied command execution."

        return await self._run(command, timeout)

    def _needs_approval(self, command: str) -> bool:
        lowered = command.lower().strip()
        for op in _DANGEROUS_OPERATORS:
            if op in lowered:
                return True
        tokens = lowered.split()
        if not tokens:
            return False
        first = tokens[0]
        if first in _DANGEROUS_PREFIXES:
            return True
        if first in _SAFE_PREFIXES:
            return False
        return True

    async def _run(self, command: str, timeout: int) -> str:
        is_windows = platform.system() == "Windows"
        try:
            if is_windows:
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=self.workspace,
                )
            else:
                shell = os.environ.get("SHELL", "/bin/sh")
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=self.workspace,
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
            return f"Command completed with exit code {proc.returncode} (no output)."

        if len(output) > 8000:
            output = output[:8000] + f"\n\n... (truncated, total {len(output)} chars)"

        return f"Exit code: {proc.returncode}\n\n{output}"
