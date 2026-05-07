"""Built-in tool layer."""

from pathlib import Path

from myagent.tools.filesystem import ListDirTool, ReadFileTool
from myagent.tools.memory import (
    MemoryAppendDailyTool,
    MemoryForgetTool,
    MemoryGetTool,
    MemoryProposeLongTermTool,
    MemorySearchTool,
)
from myagent.tools.registry import ToolRegistry


def create_default_registry(workspace: Path | str | None = None) -> ToolRegistry:
    """Create a registry with first-stage built-in tools."""
    root = Path(workspace or ".").resolve()
    registry = ToolRegistry()
    registry.register(ListDirTool(root))
    registry.register(ReadFileTool(root))
    return registry


__all__ = [
    "ListDirTool",
    "MemoryAppendDailyTool",
    "MemoryForgetTool",
    "MemoryGetTool",
    "MemoryProposeLongTermTool",
    "MemorySearchTool",
    "ReadFileTool",
    "ToolRegistry",
    "create_default_registry",
]
