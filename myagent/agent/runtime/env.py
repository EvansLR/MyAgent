"""Runtime environment text for model-visible context."""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import platform


def format_runtime_environment(
    workspace_root: Path | str | None = None,
    now: datetime | None = None,
) -> str:
    """Return runtime facts that help the model call local tools correctly."""
    root = Path(workspace_root or ".").resolve()
    current = now or datetime.now().astimezone()
    os_name = platform.system() or "Unknown"
    shell = _detect_shell(os_name)
    path_style = "Windows paths" if os_name == "Windows" else "POSIX paths"
    timezone = current.tzname() or "local timezone"
    return "\n".join(
        [
            f"- Current date: {current.date().isoformat()}",
            f"- Current time: {current.strftime('%H:%M:%S')} {timezone}",
            f"- OS: {os_name}",
            f"- Shell: {shell}",
            f"- Workspace root: {root}",
            f"- Path style: {path_style}",
            "- Resolve relative dates such as today, tomorrow, and yesterday to absolute dates before searching.",
            "- Filesystem tools resolve relative paths inside the workspace root.",
            "- Common personal folder aliases such as Desktop, Downloads, Documents, and 桌面 are recognized.",
            "- Read-only filesystem operations do not require approval.",
            "- Mutating filesystem operations outside the workspace require explicit user approval from the current channel.",
            "- Prefer relative paths such as '.' unless the user asks for a specific external location.",
            "- Do not invent absolute paths.",
        ]
    )


def _detect_shell(os_name: str) -> str:
    if os_name == "Windows":
        parent = (os.environ.get("PSModulePath") or "").lower()
        if "powershell" in parent:
            return "PowerShell"
        return "Windows shell"
    return os.environ.get("SHELL") or "Unknown shell"
