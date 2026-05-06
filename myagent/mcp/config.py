"""MCP server configuration parsing."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class McpServerConfig:
    """Configuration for one MCP server."""

    name: str
    command: str | None = None
    url: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


def parse_mcp_servers(data: dict[str, Any]) -> list[McpServerConfig]:
    """Parse ``mcpServers`` from a JSON config dictionary."""
    raw_servers = data.get("mcpServers", {})
    if not isinstance(raw_servers, dict):
        return []

    configs: list[McpServerConfig] = []
    for name, raw in raw_servers.items():
        if not isinstance(raw, dict):
            continue
        command = raw.get("command")
        url = raw.get("url")
        if not command and not url:
            continue
        args = raw.get("args", [])
        env = raw.get("env", {})
        configs.append(
            McpServerConfig(
                name=str(name),
                command=str(command) if command else None,
                url=str(url) if url else None,
                args=[str(arg) for arg in args] if isinstance(args, list) else [],
                env={str(key): str(value) for key, value in env.items()} if isinstance(env, dict) else {},
            )
        )
    return configs
