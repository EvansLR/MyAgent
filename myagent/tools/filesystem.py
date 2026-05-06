"""Read-only filesystem tools."""

from pathlib import Path
from typing import Any

from myagent.tools.base import Tool


_IGNORE_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".test-workspaces",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}


class FilesystemTool(Tool):
    """Shared path handling for workspace-scoped filesystem tools."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()

    def resolve_path(self, path: str) -> Path:
        """Resolve a path and ensure it stays inside the workspace."""
        raw = Path(path).expanduser()
        candidate = raw if raw.is_absolute() else self.workspace / raw
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.workspace)
        except ValueError as exc:
            raise PermissionError(f"Path is outside workspace: {path}") from exc
        return resolved


class ListDirTool(FilesystemTool):
    """List files and directories under the workspace."""

    @property
    def name(self) -> str:
        return "list_dir"

    @property
    def description(self) -> str:
        return "List directory contents inside the workspace."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to list."},
                "recursive": {"type": "boolean", "description": "Whether to list recursively."},
                "max_entries": {
                    "type": "integer",
                    "description": "Maximum number of entries to return.",
                    "minimum": 1,
                },
            },
            "required": ["path"],
        }

    async def execute(
        self,
        path: str,
        recursive: bool = False,
        max_entries: int = 200,
        **_: Any,
    ) -> str:
        try:
            directory = self.resolve_path(path)
            if not directory.exists():
                return f"Error: Directory not found: {path}"
            if not directory.is_dir():
                return f"Error: Not a directory: {path}"

            entries = self._recursive_entries(directory) if recursive else self._direct_entries(directory)
            total = len(entries)
            visible = entries[:max_entries]
            if not visible:
                return f"Directory is empty: {path}"
            result = "\n".join(visible)
            if total > max_entries:
                result += f"\n\n(truncated, showing {max_entries} of {total} entries)"
            return result
        except PermissionError as exc:
            return f"Error: {exc}"

    def _direct_entries(self, directory: Path) -> list[str]:
        entries: list[str] = []
        for child in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
            if child.name in _IGNORE_DIRS:
                continue
            suffix = "/" if child.is_dir() else ""
            entries.append(f"{child.name}{suffix}")
        return entries

    def _recursive_entries(self, directory: Path) -> list[str]:
        entries: list[str] = []
        for child in sorted(directory.rglob("*"), key=lambda p: str(p).lower()):
            if any(part in _IGNORE_DIRS for part in child.relative_to(directory).parts):
                continue
            suffix = "/" if child.is_dir() else ""
            entries.append(f"{child.relative_to(directory)}{suffix}")
        return entries


class ReadFileTool(FilesystemTool):
    """Read a UTF-8 text file with line numbers."""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read a UTF-8 text file inside the workspace with line numbers."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read."},
                "offset": {
                    "type": "integer",
                    "description": "1-based line number to start at.",
                    "minimum": 1,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to return.",
                    "minimum": 1,
                },
            },
            "required": ["path"],
        }

    async def execute(
        self,
        path: str,
        offset: int = 1,
        limit: int = 2000,
        **_: Any,
    ) -> str:
        try:
            file_path = self.resolve_path(path)
            if not file_path.exists():
                return f"Error: File not found: {path}"
            if not file_path.is_file():
                return f"Error: Not a file: {path}"

            lines = file_path.read_text(encoding="utf-8").splitlines()
            if not lines:
                return f"(Empty file: {path})"
            if offset > len(lines):
                return f"Error: offset {offset} is beyond end of file ({len(lines)} lines)"

            start = max(offset, 1) - 1
            end = min(start + limit, len(lines))
            numbered = [f"{line_no}| {line}" for line_no, line in enumerate(lines[start:end], start + 1)]
            result = "\n".join(numbered)
            if end < len(lines):
                result += f"\n\n(Showing lines {offset}-{end} of {len(lines)}. Use offset={end + 1} to continue.)"
            else:
                result += f"\n\n(End of file - {len(lines)} lines total)"
            return result
        except PermissionError as exc:
            return f"Error: {exc}"
