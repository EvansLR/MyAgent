from typing import Any

from myagent.mcp.registry import register_mcp_tools
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
