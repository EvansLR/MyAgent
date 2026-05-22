"""Shared runtime assembly for CLI and gateway commands."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer

from myagent.agent import AgentLoop
from myagent.agent.runtime.cron_bridge import AgentCronBridge
from myagent.bus import MessageBus
from myagent.config import Settings
from myagent.cron import CronService
from myagent.mcp import HttpMcpClient, StdioMcpClient
from myagent.mcp.registry import register_mcp_tools_with_summary
from myagent.providers import create_provider
from myagent.tools import ToolRegistry, create_default_registry
from myagent.tools.context import ApprovalCallback


@dataclass(slots=True)
class AgentRuntime:
    """Objects shared by local CLI and gateway command runners."""

    agent: AgentLoop
    registry: ToolRegistry
    mcp_clients: list[StdioMcpClient | HttpMcpClient]


async def create_agent_runtime(
    settings: Settings,
    bus: MessageBus,
    *,
    workspace_root: Path,
    approval_callback: ApprovalCallback,
    start_cron: bool,
) -> AgentRuntime:
    """Create the common provider, tool, MCP, and agent runtime."""
    registry = create_default_registry(workspace_root)
    mcp_clients = await connect_mcp_servers(settings, registry)
    cron_service = create_cron_service(bus)
    agent = AgentLoop(
        bus,
        provider=create_provider(settings),
        tool_registry=registry,
        workspace_root=workspace_root,
        cron_service=cron_service,
        start_cron=start_cron,
        approval_callback=approval_callback,
    )
    return AgentRuntime(
        agent=agent,
        registry=registry,
        mcp_clients=mcp_clients,
    )


def create_cron_service(bus: MessageBus) -> CronService:
    """Create the scheduled-task runtime for CLI and gateway entrypoints."""
    bridge = AgentCronBridge(bus)
    store_path = Path.home() / ".myagent" / "runtime" / "cron" / "jobs.json"
    return CronService(
        store_path=store_path,
        on_job=bridge.on_job,
    )


async def connect_mcp_servers(
    settings: Settings,
    registry: ToolRegistry,
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
            f"{summary.tool_count}/{summary.discovered_tool_count} tools."
        )
        clients.append(client)
    return clients
