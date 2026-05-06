from pathlib import Path
import shutil
import sys

import pytest

from myagent.mcp import McpServerConfig, StdioMcpClient


def make_workspace(name: str) -> Path:
    root = Path(".test-workspaces") / "mcp-stdio" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def write_demo_server(root: Path) -> Path:
    path = root / "demo_mcp_server.py"
    path.write_text(
        r'''
import json
import sys


def send(payload):
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    msg = json.loads(line)
    method = msg.get("method")
    if method == "initialize":
        send({
            "jsonrpc": "2.0",
            "id": msg["id"],
            "result": {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "demo", "version": "0.1.0"},
            },
        })
    elif method == "notifications/initialized":
        continue
    elif method == "tools/list":
        send({
            "jsonrpc": "2.0",
            "id": msg["id"],
            "result": {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Echo text.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"text": {"type": "string"}},
                            "required": ["text"],
                        },
                    }
                ]
            },
        })
    elif method == "tools/call":
        text = msg["params"]["arguments"]["text"]
        send({
            "jsonrpc": "2.0",
            "id": msg["id"],
            "result": {
                "content": [{"type": "text", "text": f"echo: {text}"}]
            },
        })
'''.strip(),
        encoding="utf-8",
    )
    return path


async def test_stdio_mcp_client_lists_and_calls_tools() -> None:
    root = make_workspace("demo")
    server = write_demo_server(root)
    client = StdioMcpClient(
        McpServerConfig(
            name="demo",
            command=sys.executable,
            args=[str(server)],
        )
    )

    try:
        try:
            await client.connect()
        except PermissionError as exc:
            pytest.skip(f"stdio subprocess pipes are blocked in this environment: {exc}")
        tools = await client.list_tools()
        result = await client.call_tool("echo", {"text": "hello"})
    finally:
        await client.close()

    assert tools[0].name == "echo"
    assert tools[0].description == "Echo text."
    assert tools[0].input_schema["required"] == ["text"]
    assert result == "echo: hello"
