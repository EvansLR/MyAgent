"""Tools for attaching files to the final channel response."""

from pathlib import Path
from typing import Any

from myagent.tools.base import Tool
from myagent.tools.context import ToolExecutionContext


class AttachFileTool(Tool):
    """Record an existing local file to send with the final reply."""

    def __init__(self, workspace: Path | str | None = None) -> None:
        self.workspace = Path(workspace or ".").resolve()

    @property
    def name(self) -> str:
        return "attach_file"

    @property
    def description(self) -> str:
        return (
            "Attach an existing local file to the final response. "
            "Use this after finding, creating, copying, or moving a file that "
            "the user asked to receive in the chat. This does not send a separate message."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": (
                        "Path to an existing file. Relative paths are resolved inside "
                        "the workspace; Desktop, Downloads, and Documents are supported."
                    ),
                },
            },
            "required": ["file_path"],
        }

    async def execute(
        self,
        file_path: str,
        _context: ToolExecutionContext | None = None,
        _attachments: list[str] | None = None,
        **_: Any,
    ) -> str:
        path = self._resolve_path(file_path)
        if not path.exists():
            return f"Error: Attachment file not found: {file_path}"
        if not path.is_file():
            return f"Error: Attachment path is not a file: {file_path}"

        resolved = str(path)
        attachments = _context.attachments if _context is not None else _attachments
        if attachments is not None and resolved not in attachments:
            attachments.append(resolved)
        return f"Attached file to final response: {resolved}"

    def _resolve_path(self, file_path: str) -> Path:
        known = _resolve_known_user_location(file_path)
        raw = known or Path(file_path).expanduser()
        candidate = raw if raw.is_absolute() else self.workspace / raw
        return candidate.resolve()


def _resolve_known_user_location(file_path: str) -> Path | None:
    text = file_path.strip().strip("\"'")
    mapping = {
        "desktop": Path.home() / "Desktop",
        "downloads": Path.home() / "Downloads",
        "documents": Path.home() / "Documents",
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
