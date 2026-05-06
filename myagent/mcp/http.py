"""Minimal Streamable HTTP MCP client."""

from typing import Any

import httpx

from myagent.mcp.config import McpServerConfig
from myagent.mcp.stdio import PROTOCOL_VERSION, _content_to_text
from myagent.mcp.types import McpToolDefinition


class HttpMcpClient:
    """Small JSON-RPC MCP client for URL-based Streamable HTTP servers."""

    def __init__(
        self,
        config: McpServerConfig,
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not config.url:
            raise RuntimeError("HTTP MCP server requires url.")
        self.config = config
        self.timeout = timeout
        self.client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None
        self._next_id = 1

    async def connect(self) -> None:
        """Initialize the MCP session."""
        await self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": "MyAgent",
                    "version": "0.1.0",
                },
            },
        )
        await self._notify("notifications/initialized", {})

    async def list_tools(self) -> list[McpToolDefinition]:
        """Return tools exposed by the MCP server."""
        result = await self._request("tools/list", {})
        tools = result.get("tools", []) if isinstance(result, dict) else []
        definitions: list[McpToolDefinition] = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            name = tool.get("name")
            if not name:
                continue
            definitions.append(
                McpToolDefinition(
                    name=str(name),
                    description=str(tool.get("description", "")),
                    input_schema=dict(tool.get("inputSchema", {"type": "object", "properties": {}})),
                )
            )
        return definitions

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call one MCP tool and return text content."""
        result = await self._request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments,
            },
        )
        if isinstance(result, dict) and result.get("isError"):
            return "Error: " + _content_to_text(result.get("content", []))
        if isinstance(result, dict):
            return _content_to_text(result.get("content", []))
        return str(result)

    async def close(self) -> None:
        """Close the backing HTTP client if owned by this instance."""
        if self._owns_client:
            await self.client.aclose()

    async def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        response = await self._post(payload)
        message = _parse_http_response(response, request_id)
        if "error" in message:
            raise RuntimeError(f"MCP {method} failed: {message['error']}")
        result = message.get("result", {})
        return result if isinstance(result, dict) else {"value": result}

    async def _notify(self, method: str, params: dict[str, Any]) -> None:
        await self._post(
            {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
            }
        )

    async def _post(self, payload: dict[str, Any]) -> httpx.Response:
        response = await self.client.post(
            self.config.url or "",
            json=payload,
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        return response


def _parse_http_response(response: httpx.Response, request_id: int) -> dict[str, Any]:
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        return _parse_sse_response(response.text, request_id)
    data = response.json()
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("id") == request_id:
                return item
        raise RuntimeError(f"MCP response for id {request_id} not found.")
    if isinstance(data, dict):
        return data
    raise RuntimeError("Invalid MCP HTTP response.")


def _parse_sse_response(text: str, request_id: int) -> dict[str, Any]:
    for event in text.split("\n\n"):
        data_lines = [
            line.removeprefix("data:").strip()
            for line in event.splitlines()
            if line.startswith("data:")
        ]
        if not data_lines:
            continue
        payload = "\n".join(data_lines)
        data = httpx.Response(200, content=payload).json()
        if isinstance(data, dict) and data.get("id") == request_id:
            return data
    raise RuntimeError(f"MCP SSE response for id {request_id} not found.")
