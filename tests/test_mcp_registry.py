from typing import Any

from myagent.mcp.registry import filter_mcp_tools, register_mcp_tools, register_mcp_tools_with_summary
from myagent.mcp.types import McpToolDefinition
from myagent.tools import ToolRegistry


class FakeMcpClient:
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        return f"{name}: {arguments['query']}"


async def test_register_mcp_tools_adds_prefixed_tools_to_registry() -> None:
    registry = ToolRegistry()
    tools = [
        McpToolDefinition(
            name="search",
            description="Search something.",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        )
    ]

    names = register_mcp_tools(
        registry,
        server_name="demo",
        client=FakeMcpClient(),
        tools=tools,
    )

    assert names == ["mcp_demo_search"]
    assert registry.has("mcp_demo_search")
    assert await registry.execute("mcp_demo_search", {"query": "hello"}) == "search: hello"


async def test_register_mcp_tools_with_summary_returns_observable_data() -> None:
    registry = ToolRegistry()
    tools = [
        McpToolDefinition(
            name="search",
            description="Search something.",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        )
    ]

    summary = register_mcp_tools_with_summary(
        registry,
        server_name="demo",
        transport="stdio",
        client=FakeMcpClient(),
        tools=tools,
    )

    assert summary.server_name == "demo"
    assert summary.transport == "stdio"
    assert summary.discovered_tool_count == 1
    assert summary.tool_count == 1
    assert summary.registered_tool_names == ["mcp_demo_search"]
    assert summary.skipped_tool_names == []
    assert summary.to_dict() == {
        "server_name": "demo",
        "transport": "stdio",
        "discovered_tool_count": 1,
        "tool_count": 1,
        "registered_tool_names": ["mcp_demo_search"],
        "skipped_tool_names": [],
    }


async def test_register_mcp_tools_with_summary_applies_tool_filters() -> None:
    registry = ToolRegistry()
    tools = [
        McpToolDefinition(name="search", description="", input_schema={"type": "object"}),
        McpToolDefinition(name="delete", description="", input_schema={"type": "object"}),
    ]

    summary = register_mcp_tools_with_summary(
        registry,
        server_name="demo",
        transport="stdio",
        client=FakeMcpClient(),
        tools=tools,
        include_tools=("search",),
    )

    assert summary.discovered_tool_count == 2
    assert summary.tool_count == 1
    assert summary.registered_tool_names == ["mcp_demo_search"]
    assert summary.skipped_tool_names == ["delete"]
    assert registry.has("mcp_demo_search")
    assert not registry.has("mcp_demo_delete")


def test_filter_mcp_tools_matches_registered_names_and_excludes() -> None:
    tools = [
        McpToolDefinition(name="Search Issues", description="", input_schema={"type": "object"}),
        McpToolDefinition(name="Delete Issue", description="", input_schema={"type": "object"}),
    ]

    selected, skipped = filter_mcp_tools(
        server_name="GitHub",
        tools=tools,
        include_tools=("mcp_github_search_issues", "mcp_github_delete_issue"),
        exclude_tools=("mcp_github_delete_issue",),
    )

    assert [tool.name for tool in selected] == ["Search Issues"]
    assert skipped == ["Delete Issue"]
