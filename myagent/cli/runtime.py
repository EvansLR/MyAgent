"""Shared runtime assembly for CLI and gateway commands."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

import typer

from myagent.agent import AgentLoop
from myagent.bus import MessageBus
from myagent.config import Settings
from myagent.mcp import HttpMcpClient, StdioMcpClient
from myagent.mcp.registry import register_mcp_tools_with_summary
from myagent.providers import create_provider
from myagent.tools import ToolRegistry, create_default_registry
from myagent.tracing import JsonlTraceStore, TraceStore

ApprovalCallback = Callable[[str], Awaitable[bool]]


@dataclass(slots=True)
class AgentRuntime:
    """Objects shared by local CLI and gateway command runners."""

    agent: AgentLoop
    registry: ToolRegistry
    trace_store: TraceStore
    mcp_clients: list[StdioMcpClient | HttpMcpClient]


async def create_agent_runtime(
    settings: Settings,
    bus: MessageBus,
    *,
    workspace_root: Path,
    approval_callback: ApprovalCallback,
    start_cron: bool,
) -> AgentRuntime:
    """Create the common provider, tool, trace, MCP, and agent runtime."""
    registry = create_default_registry(workspace_root, approval_callback=approval_callback)
    trace_store = JsonlTraceStore()
    mcp_clients = await connect_mcp_servers(settings, registry, trace_store=trace_store)
    agent = AgentLoop(
        bus,
        provider=create_provider(settings),
        tool_registry=registry,
        trace_store=trace_store,
        workspace_root=workspace_root,
        start_cron=start_cron,
    )
    return AgentRuntime(
        agent=agent,
        registry=registry,
        trace_store=trace_store,
        mcp_clients=mcp_clients,
    )


async def connect_mcp_servers(
    settings: Settings,
    registry: ToolRegistry,
    *,
    trace_store: TraceStore | None = None,
) -> list[StdioMcpClient | HttpMcpClient]:
    """Connect configured MCP servers and register their tools."""
    clients: list[StdioMcpClient | HttpMcpClient] = []
    for config in settings.mcp_servers:
        client = HttpMcpClient(config) if config.url else StdioMcpClient(config)
        transport = "http" if config.url else "stdio"
        try:
            await client.connect()
            tools = await client.list_tools()
        except Exception as exc:
            typer.echo(f"MyAgent: Failed to connect MCP server {config.name}: {exc}")
            trace_startup(
                trace_store,
                "mcp_server_connect_failed",
                {
                    "server_name": config.name,
                    "transport": transport,
                    "error": str(exc),
                },
            )
            await client.close()
            continue
        summary = register_mcp_tools_with_summary(
            registry,
            server_name=config.name,
            transport=transport,
            client=client,
            tools=tools,
            include_tools=config.include_tools,
            exclude_tools=config.exclude_tools,
        )
        typer.echo(
            f"MyAgent: Connected MCP server {summary.server_name} "
            f"({summary.transport}) with "
            f"{summary.tool_count}/{summary.discovered_tool_count} tools. "
            "Details saved to startup trace."
        )
        trace_startup(trace_store, "mcp_server_registered", summary.to_dict())
        clients.append(client)
    return clients


def trace_startup(
    trace_store: TraceStore | None,
    event: str,
    data: dict[str, object],
) -> None:
    if trace_store is None:
        return
    try:
        trace_store.record("runtime:startup", "startup", event, data)
    except Exception:
        pass
