"""Register MCP tool adapters into MyAgent ToolRegistry."""

from myagent.mcp.adapter import McpToolAdapter
from myagent.mcp.types import McpToolClient, McpToolDefinition
from myagent.tools import ToolRegistry


def register_mcp_tools(
    registry: ToolRegistry,
    *,
    server_name: str,
    client: McpToolClient,
    tools: list[McpToolDefinition],
) -> list[str]:
    """Adapt and register MCP tools, returning registered names."""
    registered: list[str] = []
    for definition in tools:
        adapter = McpToolAdapter(server_name, definition, client)
        registry.register(adapter)
        registered.append(adapter.name)
    return registered
