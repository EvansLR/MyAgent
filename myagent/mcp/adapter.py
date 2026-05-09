"""Adapt MCP tools to MyAgent tools."""

import re
from typing import Any

from myagent.mcp.types import McpToolClient, McpToolDefinition
from myagent.tools.base import Tool


class McpToolAdapter(Tool):
    """Expose one MCP tool through the MyAgent Tool interface."""

    def __init__(
        self,
        server_name: str,
        definition: McpToolDefinition,
        client: McpToolClient,
    ) -> None:
        self.server_name = server_name
        self.definition = definition
        self.client = client
        self._name = safe_mcp_tool_name(server_name, definition.name)

    @property
    def name(self) -> str:
        """Return the MyAgent-facing tool name."""
        return self._name

    @property
    def description(self) -> str:
        """Return the MCP tool description."""
        source = f"MCP server: {self.server_name}."
        if not self.definition.description:
            return source
        return f"{self.definition.description} ({source})"

    @property
    def parameters(self) -> dict[str, Any]:
        """Return the MCP tool input schema."""
        return self.definition.input_schema

    async def execute(self, **kwargs: Any) -> str:
        """Call the backing MCP tool."""
        return await self.client.call_tool(self.definition.name, kwargs)


def safe_mcp_tool_name(server_name: str, tool_name: str) -> str:
    """Return a stable prefixed tool name safe for LLM function calling."""
    combined = f"mcp_{server_name}_{tool_name}".lower()
    safe = re.sub(r"[^a-z0-9_]+", "_", combined)
    safe = re.sub(r"_+", "_", safe).strip("_")
    return safe or "mcp_tool"
