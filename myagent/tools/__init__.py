"""Built-in tool layer."""

from pathlib import Path

from myagent.tools.attachments import AttachFileTool
from myagent.tools.context import ApprovalCallback
from myagent.tools.filesystem import (
    CopyFileTool,
    EditFileTool,
    ListDirTool,
    MoveFileTool,
    ReadFileTool,
    WriteFileTool,
)
from myagent.tools.memory import (
    MemoryArchiveTool,
    MemoryForgetTool,
    MemoryGetTool,
    MemoryProposeTool,
    MemoryRememberTool,
    MemorySearchTool,
)
from myagent.tools.cron import CronTool
from myagent.tools.registry import ToolRegistry
from myagent.tools.skills import SkillGetTool
from myagent.tools.shell import ShellCommandTool
from myagent.tools.web import WebFetchTool, WebSearchTool


def create_default_registry(
    workspace: Path | str | None = None,
    approval_callback: ApprovalCallback | None = None,
) -> ToolRegistry:
    """Create a registry with first-stage built-in tools."""
    root = Path(workspace or ".").resolve()
    registry = ToolRegistry(approval_callback=approval_callback)
    registry.register(ListDirTool(root, approval_callback=approval_callback))
    registry.register(ReadFileTool(root, approval_callback=approval_callback))
    registry.register(WriteFileTool(root, approval_callback=approval_callback))
    registry.register(EditFileTool(root, approval_callback=approval_callback))
    registry.register(CopyFileTool(root, approval_callback=approval_callback))
    registry.register(MoveFileTool(root, approval_callback=approval_callback))
    registry.register(AttachFileTool(root))
    registry.register(WebSearchTool())
    registry.register(WebFetchTool())
    registry.register(ShellCommandTool(root, approval_callback=approval_callback))
    return registry


__all__ = [
    "AttachFileTool",
    "CopyFileTool",
    "CronTool",
    "EditFileTool",
    "ListDirTool",
    "MoveFileTool",
    "MemoryArchiveTool",
    "MemoryForgetTool",
    "MemoryGetTool",
    "MemoryProposeTool",
    "MemoryRememberTool",
    "MemorySearchTool",
    "ReadFileTool",
    "ShellCommandTool",
    "SkillGetTool",
    "ToolRegistry",
    "WebFetchTool",
    "WebSearchTool",
    "WriteFileTool",
    "create_default_registry",
]
