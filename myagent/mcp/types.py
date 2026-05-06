"""MCP tool protocol types."""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class McpToolDefinition:
    """A tool definition returned by an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]


class McpToolClient(Protocol):
    """Client contract needed by McpToolAdapter."""

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call an MCP tool and return text content."""
        ...
