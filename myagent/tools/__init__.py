"""Built-in tool layer."""

from pathlib import Path

from myagent.tools.attachments import AttachFileTool
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
    MemoryConsolidateTool,
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
) -> ToolRegistry:
    """Create a registry with first-stage built-in tools."""
    root = Path(workspace or ".").resolve()
    registry = ToolRegistry()
    registry.register(ListDirTool(root))
    registry.register(ReadFileTool(root))
    registry.register(WriteFileTool(root))
    registry.register(EditFileTool(root))
    registry.register(CopyFileTool(root))
    registry.register(MoveFileTool(root))
    registry.register(AttachFileTool(root))
    registry.register(WebSearchTool())
    registry.register(WebFetchTool())
    registry.register(ShellCommandTool(root))
    return registry


__all__ = [
    "AttachFileTool",
    "CopyFileTool",
    "CronTool",
    "EditFileTool",
    "ListDirTool",
    "MoveFileTool",
    "MemoryArchiveTool",
    "MemoryConsolidateTool",
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
