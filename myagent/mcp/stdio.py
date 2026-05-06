"""Minimal stdio MCP client."""

import asyncio
import json
import os
from typing import Any

from myagent.mcp.config import McpServerConfig
from myagent.mcp.types import McpToolDefinition

PROTOCOL_VERSION = "2025-03-26"


class StdioMcpClient:
    """Small JSON-RPC over stdio MCP client."""

    def __init__(self, config: McpServerConfig, timeout: float = 10.0) -> None:
        self.config = config
        self.timeout = timeout
        self.process: asyncio.subprocess.Process | None = None
        self._next_id = 1

    async def connect(self) -> None:
        """Start the server process and initialize the MCP session."""
        env = os.environ.copy()
        env.update(self.config.env)
        if not self.config.command:
            raise RuntimeError("stdio MCP server requires command.")
        self.process = await asyncio.create_subprocess_exec(
            self.config.command,
            *self.config.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
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
        """Terminate the server process."""
        if self.process is None:
            return
        if self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=2)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
        self.process = None

    async def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        await self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )
        response = await asyncio.wait_for(self._read_response(request_id), timeout=self.timeout)
        if "error" in response:
            raise RuntimeError(f"MCP {method} failed: {response['error']}")
        result = response.get("result", {})
        return result if isinstance(result, dict) else {"value": result}

    async def _notify(self, method: str, params: dict[str, Any]) -> None:
        await self._send(
            {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
            }
        )

    async def _send(self, payload: dict[str, Any]) -> None:
        process = self._require_process()
        if process.stdin is None:
            raise RuntimeError("MCP process stdin is not available.")
        process.stdin.write(json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n")
        await process.stdin.drain()

    async def _read_response(self, request_id: int) -> dict[str, Any]:
        process = self._require_process()
        if process.stdout is None:
            raise RuntimeError("MCP process stdout is not available.")
        while True:
            line = await process.stdout.readline()
            if not line:
                raise RuntimeError("MCP process closed stdout.")
            message = json.loads(line.decode("utf-8"))
            if message.get("id") == request_id:
                return message

    def _require_process(self) -> asyncio.subprocess.Process:
        if self.process is None:
            raise RuntimeError("MCP client is not connected.")
        return self.process


def _content_to_text(content: Any) -> str:
    if not isinstance(content, list):
        return str(content)
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text", "")))
        else:
            parts.append(json.dumps(item, ensure_ascii=False))
    return "\n".join(part for part in parts if part)
