"""Built-in tool layer."""

from pathlib import Path

from myagent.tools.filesystem import ListDirTool, ReadFileTool, WriteFileTool
from myagent.tools.memory import (
    MemoryAppendDailyTool,
    MemoryForgetTool,
    MemoryGetTool,
    MemoryProposeLongTermTool,
    MemorySearchTool,
)
from myagent.tools.registry import ToolRegistry
from myagent.tools.skills import SkillGetTool
from myagent.tools.web import WebFetchTool, WebSearchTool


def create_default_registry(workspace: Path | str | None = None) -> ToolRegistry:
    """Create a registry with first-stage built-in tools."""
    root = Path(workspace or ".").resolve()
    registry = ToolRegistry()
    registry.register(ListDirTool(root))
    registry.register(ReadFileTool(root))
    registry.register(WriteFileTool(root))
    registry.register(WebSearchTool())
    registry.register(WebFetchTool())
    return registry


__all__ = [
    "ListDirTool",
    "MemoryAppendDailyTool",
    "MemoryForgetTool",
    "MemoryGetTool",
    "MemoryProposeLongTermTool",
    "MemorySearchTool",
    "ReadFileTool",
    "SkillGetTool",
    "ToolRegistry",
    "WebFetchTool",
    "WebSearchTool",
    "WriteFileTool",
    "create_default_registry",
]
