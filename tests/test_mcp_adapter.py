from typing import Any

from myagent.mcp import McpToolAdapter, McpToolDefinition, safe_mcp_tool_name


class FakeMcpClient:
    def __init__(self) -> None:
        self.calls = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, arguments))
        return f"called {name}"


def make_definition() -> McpToolDefinition:
    return McpToolDefinition(
        name="Search Issues",
        description="Search repository issues.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
    )


def test_safe_mcp_tool_name_prefixes_and_sanitizes() -> None:
    assert safe_mcp_tool_name("GitHub Server", "Search Issues") == "mcp_github_server_search_issues"


async def test_mcp_tool_adapter_exposes_tool_schema_and_calls_client() -> None:
    client = FakeMcpClient()
    adapter = McpToolAdapter("github", make_definition(), client)

    result = await adapter.execute(query="bug")

    assert adapter.name == "mcp_github_search_issues"
    assert adapter.description == "Search repository issues. (MCP server: github.)"
    assert adapter.parameters["required"] == ["query"]
    assert result == "called Search Issues"
    assert client.calls == [("Search Issues", {"query": "bug"})]
