"""Workspace-scoped filesystem tools."""

from pathlib import Path
import shutil
from typing import Any

from myagent.tools.base import Tool
from myagent.tools.context import (
    ApprovalCallback,
    ToolExecutionContext,
    call_approval_callback,
)


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
    """Shared path handling and approval for filesystem tools."""

    def __init__(
        self,
        workspace: Path,
        approval_callback: ApprovalCallback | None = None,
        allowed_roots: list[Path] | None = None,
    ) -> None:
        self.workspace = workspace.resolve()
        self.approval_callback = approval_callback
        self.allowed_roots = [path.resolve() for path in (allowed_roots or [])]

    def resolve_path(self, path: str) -> Path:
        """Resolve a path and ensure it stays inside the workspace."""
        resolved = self.resolve_any_path(path)
        try:
            resolved.relative_to(self.workspace)
        except ValueError as exc:
            raise PermissionError(
                f"Path is outside workspace: {path}. "
                f"Workspace root: {self.workspace}. "
                "Use a relative path such as '.' unless the user provided an explicit in-workspace path."
            ) from exc
        return resolved

    def resolve_any_path(self, path: str) -> Path:
        """Resolve a path without enforcing the workspace boundary."""
        raw = _resolve_known_user_location(path) or Path(path).expanduser()
        candidate = raw if raw.is_absolute() else self.workspace / raw
        return candidate.resolve()

    def is_allowed_path(self, path: Path) -> bool:
        """Return whether a resolved path is inside an allowed root."""
        return any(_is_relative_to(path, root) for root in [self.workspace, *self.allowed_roots])

    async def request_approval(
        self,
        prompt: str,
        context: ToolExecutionContext | None = None,
    ) -> bool:
        """Ask the current channel to approve a higher-risk operation."""
        if context is not None:
            return await context.request_approval(prompt)
        if self.approval_callback is None:
            return False
        return await call_approval_callback(self.approval_callback, prompt, None)

    async def require_path_access(
        self,
        action: str,
        paths: list[tuple[str, Path]],
        context: ToolExecutionContext | None = None,
    ) -> str | None:
        """Return an error message unless access to all paths is allowed."""
        disallowed_paths = [(label, path) for label, path in paths if not self.is_allowed_path(path)]
        if not disallowed_paths:
            return None
        if context is None and self.approval_callback is None:
            return (
                f"Error: {action} outside the workspace requires user approval, "
                "but no approval callback is configured."
            )
        lines = [
            f"Action: {action}",
            f"Workspace: {self.workspace}",
        ]
        lines.extend(f"{label}: {path}" for label, path in disallowed_paths)
        lines.append("Risk: this operation changes files outside the workspace.")
        approved = await self.request_approval("\n".join(lines), context)
        if not approved:
            return f"Error: User denied {action} approval."
        return None

    def display_path(self, path: Path) -> str:
        """Return a compact path for tool results."""
        try:
            return str(path.relative_to(self.workspace))
        except ValueError:
            return str(path)

    def _format_allowed_roots(self) -> str:
        roots = [self.workspace, *self.allowed_roots]
        return ", ".join(str(root) for root in roots)

    def ensure_external_parent_exists(self, path: Path) -> str | None:
        """Do not silently create guessed external directories."""
        if _is_relative_to(path, self.workspace):
            return None
        if path.parent.exists():
            return None
        return f"Error: Destination directory does not exist: {path.parent}"

    async def prepare_file_transfer(
        self,
        action: str,
        source_path: str,
        destination_path: str,
        overwrite: bool,
        context: ToolExecutionContext | None = None,
    ) -> tuple[Path | None, Path | None, str | None]:
        """Resolve and validate shared copy/move source and destination rules."""
        source = self.resolve_any_path(source_path)
        destination = self.resolve_any_path(destination_path)

        if not source.exists():
            return None, None, f"Error: Source file not found: {source_path}"
        if not source.is_file():
            return None, None, f"Error: Source is not a file: {source_path}"
        if destination.exists() and destination.is_dir():
            destination = destination / source.name
        if destination.exists() and not overwrite:
            return (
                None,
                None,
                f"Error: Destination already exists: {destination}. "
                f"Call {action} with overwrite=true if replacing it is intended.",
            )
        error = await self.require_path_access(
            action,
            [("Source", source), ("Destination", destination)],
            context,
        )
        if error is not None:
            return None, None, error
        parent_error = self.ensure_external_parent_exists(destination)
        if parent_error is not None:
            return None, None, parent_error
        return source, destination, None


def _resolve_known_user_location(path: str) -> Path | None:
    text = path.strip().strip("\"'")
    mapping = {
        "desktop": Path.home() / "Desktop",
        "桌面": Path.home() / "Desktop",
        "downloads": Path.home() / "Downloads",
        "下载": Path.home() / "Downloads",
        "documents": Path.home() / "Documents",
        "文档": Path.home() / "Documents",
    }
    direct = mapping.get(text.lower())
    if direct is not None:
        return direct
    parts = Path(text).parts
    if not parts:
        return None
    root = mapping.get(parts[0].lower())
    if root is None:
        return None
    return root.joinpath(*parts[1:])


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


class ListDirTool(FilesystemTool):
    """List files and directories under the workspace."""

    @property
    def name(self) -> str:
        return "list_dir"

    @property
    def description(self) -> str:
        return (
            "List directory contents. Relative paths are resolved inside the workspace. "
            "This read-only operation does not require approval."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Directory path inside the workspace. Use '.' for the workspace root. "
                        "Use Desktop, Downloads, or Documents for common personal folders."
                    ),
                },
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
        directory = self.resolve_any_path(path)
        if not directory.exists():
            return (
                f"Error: Directory not found: {path}. "
                "Use path='.' to inspect the workspace root."
            )
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

    _MAX_CHARS = 128_000
    _DEFAULT_LIMIT = 2000

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "Read a UTF-8 text file with line numbers. Relative paths are resolved inside "
            "the workspace. This read-only operation does not require approval."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "File path inside the workspace. Prefer relative paths. "
                        "Use Desktop, Downloads, or Documents for common personal folders."
                    ),
                },
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
        limit: int | None = None,
        **_: Any,
    ) -> str:
        file_path = self.resolve_any_path(path)
        if not file_path.exists():
            return (
                f"Error: File not found: {path}. "
                "Use list_dir path='.' to inspect the workspace root first."
            )
        if not file_path.is_file():
            return f"Error: Not a file: {path}"

        lines = file_path.read_text(encoding="utf-8").splitlines()
        if not lines:
            return f"(Empty file: {path})"
        if offset > len(lines):
            return f"Error: offset {offset} is beyond end of file ({len(lines)} lines)"

        start = max(offset, 1) - 1
        end = min(start + (limit or self._DEFAULT_LIMIT), len(lines))
        numbered = [f"{line_no}| {line}" for line_no, line in enumerate(lines[start:end], start + 1)]
        result = "\n".join(numbered)
        truncated_line: int | None = None
        if len(result) > self._MAX_CHARS:
            trimmed: list[str] = []
            char_count = 0
            for line in numbered:
                next_count = char_count + len(line) + 1
                if next_count > self._MAX_CHARS:
                    break
                trimmed.append(line)
                char_count = next_count
            if trimmed:
                end = start + len(trimmed)
                result = "\n".join(trimmed)
            else:
                marker = " ... [line truncated to fit read_file response budget]"
                result = numbered[0][: max(self._MAX_CHARS - len(marker), 1)].rstrip() + marker
                end = start + 1
                truncated_line = start + 1
        if end < len(lines):
            if truncated_line is not None:
                result += f"\n\n(Line {truncated_line} was truncated to fit the response budget.)"
            result += f"\n\n(Showing lines {offset}-{end} of {len(lines)}. Use offset={end + 1} to continue.)"
        elif truncated_line is not None:
            result += (
                f"\n\n(End of file - {len(lines)} lines total; "
                f"line {truncated_line} was truncated to fit the response budget)"
            )
        else:
            result += f"\n\n(End of file - {len(lines)} lines total)"
        return result


class WriteFileTool(FilesystemTool):
    """Write a UTF-8 text file inside the workspace."""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return (
            "Write UTF-8 text content to a file. Relative paths are resolved inside the "
            "workspace. Absolute paths outside the workspace require user approval."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "File path inside the workspace. Prefer relative paths. "
                        "Parent directories will be created when needed. "
                        "Use Desktop, Downloads, or Documents for common personal folders; "
                        "these external locations require user approval."
                    ),
                },
                "content": {
                    "type": "string",
                    "description": "UTF-8 text content to write.",
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Whether to replace an existing file. Defaults to false.",
                },
            },
            "required": ["path", "content"],
        }

    async def execute(
        self,
        path: str,
        content: str,
        overwrite: bool = False,
        _context: ToolExecutionContext | None = None,
        **_: Any,
    ) -> str:
        try:
            file_path = self.resolve_any_path(path)
            if file_path.exists() and file_path.is_dir():
                return f"Error: Not a file: {path}"
            if file_path.exists() and not overwrite:
                return (
                    f"Error: File already exists: {path}. "
                    "Call write_file with overwrite=true if replacing it is intended."
                )
            error = await self.require_path_access(
                "write_file",
                [("Path", file_path)],
                _context,
            )
            if error is not None:
                return error
            parent_error = self.ensure_external_parent_exists(file_path)
            if parent_error is not None:
                return parent_error

            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"Wrote {len(content)} characters to {self.display_path(file_path)}."
        except PermissionError as exc:
            return f"Error: {exc}"


class EditFileTool(FilesystemTool):
    """Edit a UTF-8 text file by exact string replacement."""

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return (
            "Edit a UTF-8 text file by replacing exact text. Relative paths are resolved "
            "inside the workspace. Absolute paths outside the workspace require user approval."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "File path. Prefer relative workspace paths. "
                        "Use Desktop, Downloads, or Documents for common personal folders; "
                        "these external locations require user approval."
                    ),
                },
                "old_text": {
                    "type": "string",
                    "description": "Exact text to replace. Include enough context to be unique.",
                },
                "new_text": {
                    "type": "string",
                    "description": "Replacement text.",
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "Whether to replace all occurrences. Defaults to false.",
                },
            },
            "required": ["path", "old_text", "new_text"],
        }

    async def execute(
        self,
        path: str,
        old_text: str,
        new_text: str,
        replace_all: bool = False,
        _context: ToolExecutionContext | None = None,
        **_: Any,
    ) -> str:
        try:
            file_path = self.resolve_any_path(path)
            if not file_path.exists():
                return (
                    f"Error: File not found: {path}. "
                    "Use list_dir path='.' to inspect the workspace root first."
                )
            if not file_path.is_file():
                return f"Error: Not a file: {path}"
            if old_text == "":
                return "Error: old_text must not be empty."
            error = await self.require_path_access(
                "edit_file",
                [("Path", file_path)],
                _context,
            )
            if error is not None:
                return error

            content = file_path.read_text(encoding="utf-8")
            occurrences = content.count(old_text)
            if occurrences == 0:
                return "Error: old_text was not found in the file."
            if occurrences > 1 and not replace_all:
                return (
                    f"Error: old_text matched {occurrences} occurrences. "
                    "Provide more surrounding context or set replace_all=true."
                )

            if replace_all:
                updated = content.replace(old_text, new_text)
            else:
                updated = content.replace(old_text, new_text, 1)
            file_path.write_text(updated, encoding="utf-8")
            replaced = occurrences if replace_all else 1
            return f"Edited {self.display_path(file_path)}: replaced {replaced} occurrence(s)."
        except PermissionError as exc:
            return f"Error: {exc}"


class CopyFileTool(FilesystemTool):
    """Copy a file, asking for approval when paths leave the workspace."""

    @property
    def name(self) -> str:
        return "copy_file"

    @property
    def description(self) -> str:
        return (
            "Copy a file. Relative paths are resolved inside the current workspace. "
            "Use Desktop, Downloads, or Documents for common personal folders; "
            "these external locations require user approval."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "Source file path. Prefer a workspace-relative path.",
                },
                "destination_path": {
                    "type": "string",
                    "description": (
                        "Destination file path. Use Desktop, Downloads, or Documents "
                        "for common personal folders; these external locations require user approval."
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Whether to replace an existing destination file. Defaults to false.",
                },
            },
            "required": ["source_path", "destination_path"],
        }

    async def execute(
        self,
        source_path: str,
        destination_path: str,
        overwrite: bool = False,
        _context: ToolExecutionContext | None = None,
        **_: Any,
    ) -> str:
        source, destination, error = await self.prepare_file_transfer(
            "copy_file",
            source_path,
            destination_path,
            overwrite,
            _context,
        )
        if error is not None:
            return error

        try:
            assert source is not None
            assert destination is not None
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            return f"Copied {source} to {destination}."
        except PermissionError as exc:
            return f"Error: {exc}"


class MoveFileTool(FilesystemTool):
    """Move a file between allowed file locations."""

    @property
    def name(self) -> str:
        return "move_file"

    @property
    def description(self) -> str:
        return (
            "Move a file. Relative paths are resolved inside the current workspace. "
            "Use Desktop, Downloads, or Documents for common personal folders; "
            "these external locations require user approval."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "Source file path. Prefer a workspace-relative path.",
                },
                "destination_path": {
                    "type": "string",
                    "description": (
                        "Destination file path. Use Desktop, Downloads, or Documents "
                        "for common personal folders; these external locations require user approval."
                    ),
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Whether to replace an existing destination file. Defaults to false.",
                },
            },
            "required": ["source_path", "destination_path"],
        }

    async def execute(
        self,
        source_path: str,
        destination_path: str,
        overwrite: bool = False,
        _context: ToolExecutionContext | None = None,
        **_: Any,
    ) -> str:
        source, destination, error = await self.prepare_file_transfer(
            "move_file",
            source_path,
            destination_path,
            overwrite,
            _context,
        )
        if error is not None:
            return error

        try:
            assert source is not None
            assert destination is not None
            if destination.exists() and overwrite:
                destination.unlink()
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            return f"Moved {source} to {destination}."
        except PermissionError as exc:
            return f"Error: {exc}"
