"""Tool registry."""

from typing import Any

from myagent.tools.base import Tool
from myagent.tools.context import ApprovalCallback, ToolExecutionContext


class ToolRegistry:
    """Register, describe, validate, and execute tools."""

    def __init__(self, approval_callback: ApprovalCallback | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self.approval_callback = approval_callback

    def register(self, tool: Tool) -> None:
        """Register or replace one tool."""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Remove a tool by name."""
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        """Return a tool by name."""
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        """Return whether a tool exists."""
        return name in self._tools

    def get_definitions(self) -> list[dict[str, Any]]:
        """Return OpenAI-compatible tool definitions."""
        return [tool.to_schema() for tool in self._tools.values()]

    async def execute(
        self,
        name: str,
        params: dict[str, Any],
        context: ToolExecutionContext | None = None,
    ) -> str:
        """Execute a registered tool with validation."""
        tool = self.get(name)
        if tool is None:
            return f"Error: Tool '{name}' not found. Available: {', '.join(self.tool_names)}"

        casted = tool.cast_params(params)
        errors = tool.validate_params(casted)
        if errors:
            return f"Error: Invalid parameters for tool '{name}': " + "; ".join(errors)

        try:
            if context is not None:
                casted["_context"] = context
            return await tool.execute(**casted)
        except Exception as exc:  # pragma: no cover - tools should usually return errors
            return f"Error executing {name}: {exc}"

    @property
    def tool_names(self) -> list[str]:
        """Return registered tool names."""
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return self.has(name)
