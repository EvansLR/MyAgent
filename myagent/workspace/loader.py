"""Load agent workspace files from the runtime state directory."""

from pathlib import Path
from typing import Any


DEFAULT_WORKSPACE_PATH = Path.home() / ".myagent" / "workspace"

WORKSPACE_FILES = {
    "agent": "AGENT.md",
    "user": "USER.md",
    "tools": "TOOLS.md",
    "memory": "MEMORY.md",
}


class WorkspaceLoader:
    """Read personal assistant workspace files and expose them to ContextBuilder."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else DEFAULT_WORKSPACE_PATH
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Create the workspace directory if it does not exist."""
        self.root.mkdir(parents=True, exist_ok=True)

    def load_file(self, filename: str) -> str:
        """Return the contents of a workspace file, or empty string if missing."""
        path = self.root / filename
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""

    def load_all(self) -> dict[str, str]:
        """Return all present workspace files keyed by logical name."""
        return {
            key: self.load_file(filename)
            for key, filename in WORKSPACE_FILES.items()
        }

    def exists(self, filename: str) -> bool:
        """Check whether a workspace file exists."""
        return (self.root / filename).exists()

    def present_files(self) -> list[str]:
        """Return the list of workspace files that currently exist."""
        return [
            filename
            for filename in WORKSPACE_FILES.values()
            if self.exists(filename)
        ]

    def missing_files(self) -> list[str]:
        """Return the list of workspace files that do not exist."""
        return [
            filename
            for filename in WORKSPACE_FILES.values()
            if not self.exists(filename)
        ]

    def to_trace_data(self) -> dict[str, Any]:
        """Return summary data for trace events."""
        return {
            "workspace_root": str(self.root),
            "files_present": self.present_files(),
            "files_missing": self.missing_files(),
        }
