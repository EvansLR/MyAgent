"""Typer entrypoint for the local CLI channel."""

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.markdown import Markdown
import typer

from myagent.agent import AgentLoop
from myagent.bus import InboundMessage, MessageBus
from myagent.config import Settings
from myagent.mcp import HttpMcpClient, StdioMcpClient
from myagent.mcp.registry import register_mcp_tools_with_summary
from myagent.providers import create_provider
from myagent.tools import create_default_registry
from myagent.tracing import JsonlTraceStore, TraceStore

DEFAULT_SENDER_ID = "local-user"
DEFAULT_CHAT_ID = "default"
SUPPORTED_COMMANDS = {"/help", "/new", "/stop"}
CONSOLE = Console()


@dataclass(slots=True)
class CliState:
    """Mutable state owned by the local CLI channel."""

    sender_id: str = DEFAULT_SENDER_ID
    chat_id: str = DEFAULT_CHAT_ID
    session_index: int = 0
    running: bool = True

    def start_new_session(self) -> str:
        """Switch to a new local chat id and return it."""
        self.session_index += 1
        self.chat_id = f"session-{self.session_index}"
        return self.chat_id


def parse_cli_command(raw: str) -> str:
    """Classify raw CLI input as a supported command or a normal message."""
    text = raw.strip()
    if text in SUPPORTED_COMMANDS:
        return text.removeprefix("/")
    if text.startswith("/"):
        return "unknown"
    return "message"


def make_inbound_message(content: str, state: CliState) -> InboundMessage:
    """Convert user text into the message format consumed by AgentLoop."""
    return InboundMessage(
        channel="cli",
        sender_id=state.sender_id,
        chat_id=state.chat_id,
        content=content,
    )


def make_help_text() -> str:
    """Return the built-in CLI command help."""
    return "\n".join(
        [
            "MyAgent commands:",
            "  /help  Show this help message.",
            "  /new   Start a new local session.",
            "  /stop  Exit the CLI.",
        ]
    )


def handle_cli_command(command: str, state: CliState) -> str:
    """Apply a parsed CLI command and return text to print."""
    if command == "help":
        return make_help_text()
    if command == "new":
        chat_id = state.start_new_session()
        return f"Started a new session: cli:{chat_id}"
    if command == "stop":
        state.running = False
        return "Stopping MyAgent CLI."
    if command == "unknown":
        return "Unknown command. Type /help for supported commands."
    raise ValueError(f"Unsupported CLI command: {command}")


async def run_chat(
    bus: MessageBus,
    *,
    state: CliState | None = None,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = typer.echo,
) -> None:
    """Run the local interactive chat loop."""
    state = state or CliState()
    output_func("MyAgent CLI is ready. Type /help for commands.")

    while state.running:
        raw = await asyncio.to_thread(input_func, "You: ")
        command = parse_cli_command(raw)

        if command != "message":
            output_func(handle_cli_command(command, state))
            continue

        if not raw.strip():
            continue

        await bus.publish_inbound(make_inbound_message(raw, state))
        await _consume_turn_outputs(bus, output_func)


async def _consume_turn_outputs(
    bus: MessageBus,
    output_func: Callable[[str], None],
) -> None:
    """Print status updates and the final reply for one user turn."""
    if not _should_use_spinner(output_func):
        while True:
            outbound = await bus.consume_outbound()
            if outbound.metadata.get("kind") == "status":
                output_func(f"MyAgent: {outbound.content}")
                continue
            _print_final_reply(outbound.content, output_func)
            break
        return

    with CONSOLE.status("[bold cyan]MyAgent:[/bold cyan] Thinking", spinner="dots") as status:
        while True:
            outbound = await bus.consume_outbound()
            if outbound.metadata.get("kind") == "status":
                status.update(f"[bold cyan]MyAgent:[/bold cyan] {outbound.content}")
                continue

            status.stop()
            _print_final_reply(outbound.content, output_func)
            break


def _should_use_spinner(output_func: Callable[[str], None]) -> bool:
    """Return whether this run should render status updates as a spinner."""
    return output_func is typer.echo and sys.stdout.isatty()


def _print_final_reply(content: str, output_func: Callable[[str], None]) -> None:
    """Print the final answer, rendering Markdown in an interactive terminal."""
    if _should_use_rich_output(output_func):
        CONSOLE.print("[bold cyan]MyAgent:[/bold cyan]")
        CONSOLE.print(Markdown(content))
        return
    output_func(f"MyAgent: {content}")


def _should_use_rich_output(output_func: Callable[[str], None]) -> bool:
    """Return whether final replies should use Rich terminal rendering."""
    return output_func is typer.echo and sys.stdout.isatty()


async def run_local_chat(settings: Settings | None = None, config_path: str | None = None) -> None:
    """Run CLI + MessageBus + AgentLoop with the configured provider."""
    settings = settings or Settings.from_sources(config_path)
    bus = MessageBus()
    workspace_root = Path.cwd()
    registry = create_default_registry(workspace_root)
    trace_store = JsonlTraceStore()
    mcp_clients = await _connect_mcp_servers(settings, registry, trace_store=trace_store)
    agent = AgentLoop(
        bus,
        provider=create_provider(settings),
        tool_registry=registry,
        trace_store=trace_store,
        workspace_root=workspace_root,
    )
    agent_task = asyncio.create_task(agent.run_until_stopped())
    try:
        await run_chat(bus)
    finally:
        agent.stop()
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass
        for client in mcp_clients:
            await client.close()


async def _connect_mcp_servers(
    settings: Settings,
    registry,
    *,
    trace_store: TraceStore | None = None,
) -> list:
    """Connect configured MCP servers and register their tools."""
    clients: list[StdioMcpClient] = []
    for config in settings.mcp_servers:
        client = HttpMcpClient(config) if config.url else StdioMcpClient(config)
        transport = "http" if config.url else "stdio"
        try:
            await client.connect()
            tools = await client.list_tools()
        except Exception as exc:
            typer.echo(f"MyAgent: Failed to connect MCP server {config.name}: {exc}")
            _trace_startup(
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
            f"({summary.transport}) with {summary.tool_count}/{summary.discovered_tool_count} tools. "
            "Details saved to startup trace."
        )
        _trace_startup(trace_store, "mcp_server_registered", summary.to_dict())
        clients.append(client)
    return clients


def _trace_startup(
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


app = typer.Typer(
    name="myagent",
    help="MyAgent - lightweight ReAct agent runtime.",
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def main(
    config: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to a myagent JSON config file.",
    ),
) -> None:
    """Run the local CLI channel."""
    asyncio.run(run_local_chat(config_path=config))
