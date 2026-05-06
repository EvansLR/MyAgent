import json

import httpx

from myagent.mcp import HttpMcpClient, McpServerConfig


def make_client(handler) -> HttpMcpClient:
    transport = httpx.MockTransport(handler)
    return HttpMcpClient(
        McpServerConfig(name="demo", url="https://example.test/mcp"),
        client=httpx.AsyncClient(transport=transport),
    )


def json_response(request: httpx.Request) -> httpx.Response:
    payload = json.loads(request.content.decode("utf-8"))
    method = payload["method"]
    request_id = payload.get("id")
    if method == "initialize":
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "demo", "version": "0.1.0"},
                },
            },
        )
    if method == "notifications/initialized":
        return httpx.Response(202, json={})
    if method == "tools/list":
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": request_id,
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
            },
        )
    if method == "tools/call":
        text = payload["params"]["arguments"]["text"]
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": f"echo: {text}"}],
                },
            },
        )
    raise AssertionError(f"unexpected method {method}")


async def test_http_mcp_client_lists_and_calls_tools_from_json_response() -> None:
    client = make_client(json_response)

    try:
        await client.connect()
        tools = await client.list_tools()
        result = await client.call_tool("echo", {"text": "hello"})
    finally:
        await client.close()

    assert tools[0].name == "echo"
    assert tools[0].description == "Echo text."
    assert result == "echo: hello"


def sse_response(request: httpx.Request) -> httpx.Response:
    payload = json.loads(request.content.decode("utf-8"))
    request_id = payload.get("id")
    if payload["method"] == "notifications/initialized":
        return httpx.Response(202, json={})
    data = {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {"tools": []},
    }
    return httpx.Response(
        200,
        headers={"content-type": "text/event-stream"},
        content=f"event: message\ndata: {json.dumps(data)}\n\n",
    )


async def test_http_mcp_client_parses_sse_response() -> None:
    client = make_client(sse_response)

    try:
        await client.connect()
        tools = await client.list_tools()
    finally:
        await client.close()

    assert tools == []
