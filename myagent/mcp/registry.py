"""Register MCP tool adapters into MyAgent ToolRegistry."""

from dataclasses import dataclass

from myagent.mcp.adapter import McpToolAdapter
from myagent.mcp.adapter import safe_mcp_tool_name
from myagent.mcp.types import McpToolClient, McpToolDefinition
from myagent.tools import ToolRegistry


@dataclass(frozen=True, slots=True)
class McpRegistrationSummary:
    """Summary of one MCP server registration pass."""

    server_name: str
    transport: str
    discovered_tool_count: int
    tool_count: int
    registered_tool_names: list[str]
    skipped_tool_names: list[str]

    def to_dict(self) -> dict[str, object]:
        """Return CLI-friendly registration data."""
        return {
            "server_name": self.server_name,
            "transport": self.transport,
            "discovered_tool_count": self.discovered_tool_count,
            "tool_count": self.tool_count,
            "registered_tool_names": list(self.registered_tool_names),
            "skipped_tool_names": list(self.skipped_tool_names),
        }


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


def register_mcp_tools_with_summary(
    registry: ToolRegistry,
    *,
    server_name: str,
    transport: str,
    client: McpToolClient,
    tools: list[McpToolDefinition],
    include_tools: tuple[str, ...] = (),
    exclude_tools: tuple[str, ...] = (),
) -> McpRegistrationSummary:
    """Register MCP tools and return a registration summary."""
    selected_tools, skipped_tool_names = filter_mcp_tools(
        server_name=server_name,
        tools=tools,
        include_tools=include_tools,
        exclude_tools=exclude_tools,
    )
    registered = register_mcp_tools(
        registry,
        server_name=server_name,
        client=client,
        tools=selected_tools,
    )
    return McpRegistrationSummary(
        server_name=server_name,
        transport=transport,
        discovered_tool_count=len(tools),
        tool_count=len(registered),
        registered_tool_names=registered,
        skipped_tool_names=skipped_tool_names,
    )


def filter_mcp_tools(
    *,
    server_name: str,
    tools: list[McpToolDefinition],
    include_tools: tuple[str, ...] = (),
    exclude_tools: tuple[str, ...] = (),
) -> tuple[list[McpToolDefinition], list[str]]:
    """Filter MCP tools by original or registered tool name."""
    include = {item.lower() for item in include_tools}
    exclude = {item.lower() for item in exclude_tools}
    selected: list[McpToolDefinition] = []
    skipped: list[str] = []
    for definition in tools:
        original = definition.name.lower()
        registered = safe_mcp_tool_name(server_name, definition.name).lower()
        if include and original not in include and registered not in include:
            skipped.append(definition.name)
            continue
        if original in exclude or registered in exclude:
            skipped.append(definition.name)
            continue
        selected.append(definition)
    return selected, skipped
