"""Typer entrypoint for the local CLI channel."""

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, cast

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
import typer

from myagent.agent import AgentLoop
from myagent.bus import InboundMessage, MessageBus, OutboundMessage
from myagent.config import Settings
from myagent.mcp import HttpMcpClient, StdioMcpClient
from myagent.mcp.registry import register_mcp_tools_with_summary
from myagent.providers import create_provider
from myagent.tools import create_default_registry
from myagent.tracing import (
    JsonlTraceStore,
    TraceStore,
    format_context_summary,
    format_trace_events,
    format_turn_summary,
    latest_context_event,
    latest_turn_summary,
    read_trace_events,
    write_trace_report,
    write_trace_viewer,
)

DEFAULT_SENDER_ID = "local-user"
DEFAULT_CHAT_ID = "default"
SUPPORTED_COMMANDS = {"/help", "/new", "/stop"}
CONSOLE = Console()
DEFAULT_TRACE_SESSION = "cli:default"
SKILLS_TRACE_SESSION = "runtime:skills"
STARTUP_TRACE_SESSION = "runtime:startup"


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
            if outbound.metadata.get("kind") == "approval_request":
                await _handle_approval_request(outbound, output_func)
                continue
            if outbound.metadata.get("kind") == "status":
                output_func(f"MyAgent: {outbound.content}")
                continue
            _print_final_reply(outbound.content, output_func)
            break
        return

    with CONSOLE.status("[bold cyan]MyAgent:[/bold cyan] Thinking", spinner="dots") as status:
        while True:
            outbound = await bus.consume_outbound()
            if outbound.metadata.get("kind") == "approval_request":
                status.stop()
                await _handle_approval_request(outbound, output_func)
                status.start()
                status.update("[bold cyan]MyAgent:[/bold cyan] Thinking")
                continue
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


async def _handle_approval_request(
    outbound: OutboundMessage,
    output_func: Callable[[str], None],
) -> None:
    """Ask the CLI user to approve a pending tool action."""
    future = cast(asyncio.Future[bool] | None, outbound.metadata.get("future"))
    if future is None or future.done():
        return
    approved = await asyncio.to_thread(_prompt_for_approval, outbound.content, output_func)
    future.set_result(approved)


def _prompt_for_approval(prompt: str, output_func: Callable[[str], None]) -> bool:
    """Render a clear local approval prompt and return the user's decision."""
    if _should_use_rich_output(output_func):
        CONSOLE.print(_approval_panel(prompt))
        answer = CONSOLE.input("[bold yellow]Allow once?[/bold yellow] [y/N]: ")
    else:
        output_func(format_approval_prompt(prompt))
        answer = input("Allow once? [y/N]: ")
    return answer.strip().lower() in {"y", "yes"}


def format_approval_prompt(prompt: str) -> str:
    """Return a readable plain-text permission prompt."""
    return "\n".join(
        [
            "Permission request",
            "------------------",
            prompt,
            "",
            "Choose y to allow this one action, or press Enter to deny.",
        ]
    )


def _approval_panel(prompt: str) -> Panel:
    """Return a Rich panel for a permission request."""
    body = Text()
    body.append(prompt)
    body.append("\n\nChoose y to allow this one action, or press Enter to deny.", style="dim")
    return Panel(
        body,
        title="Permission request",
        border_style="yellow",
        expand=False,
    )


async def run_local_chat(settings: Settings | None = None, config_path: str | None = None) -> None:
    """Run CLI + MessageBus + AgentLoop with the configured provider."""
    settings = settings or Settings.from_sources(config_path)
    bus = MessageBus()
    workspace_root = Path.cwd()
    registry = create_default_registry(workspace_root, approval_callback=_make_cli_approval_callback(bus))
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


def _make_cli_approval_callback(bus: MessageBus):
    async def approve(prompt: str) -> bool:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()
        await bus.publish_outbound(
            OutboundMessage(
                channel="cli",
                chat_id=DEFAULT_CHAT_ID,
                content=prompt,
                metadata={
                    "kind": "approval_request",
                    "future": future,
                },
            )
        )
        return await future

    return approve


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
trace_app = typer.Typer(help="Inspect local JSONL trace files.")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    config: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to a myagent JSON config file.",
    ),
) -> None:
    """Run the local CLI channel."""
    if ctx.invoked_subcommand is not None:
        return
    asyncio.run(run_local_chat(config_path=config))


@trace_app.command("latest")
def trace_latest(
    session: str = typer.Option(
        DEFAULT_TRACE_SESSION,
        "--session",
        "-s",
        help="Trace session key, for example cli:default.",
    ),
    trace_dir: Path = typer.Option(
        Path("data/traces"),
        "--trace-dir",
        help="Directory containing JSONL trace files.",
    ),
) -> None:
    """Show a compact summary of the latest turn in a session trace."""
    events = read_trace_events(session, trace_dir)
    if not events:
        typer.echo(f"No trace events found for session {session!r} in {trace_dir}.")
        raise typer.Exit(code=1)
    summary = latest_turn_summary(events)
    if summary is None:
        typer.echo(f"No turns found for session {session!r}.")
        raise typer.Exit(code=1)
    typer.echo(format_turn_summary(summary))


@trace_app.command("show")
def trace_show(
    session: str = typer.Option(
        DEFAULT_TRACE_SESSION,
        "--session",
        "-s",
        help="Trace session key, for example cli:default.",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        help="Number of recent events to show.",
    ),
    trace_dir: Path = typer.Option(
        Path("data/traces"),
        "--trace-dir",
        help="Directory containing JSONL trace files.",
    ),
) -> None:
    """Show recent events for a session trace."""
    events = read_trace_events(session, trace_dir)
    if not events:
        typer.echo(f"No trace events found for session {session!r} in {trace_dir}.")
        raise typer.Exit(code=1)
    typer.echo(format_trace_events(events, limit=limit))


@trace_app.command("context")
def trace_context(
    session: str = typer.Option(
        DEFAULT_TRACE_SESSION,
        "--session",
        "-s",
        help="Trace session key, for example cli:default.",
    ),
    trace_dir: Path = typer.Option(
        Path("data/traces"),
        "--trace-dir",
        help="Directory containing JSONL trace files.",
    ),
) -> None:
    """Show the latest ContextBuilder assembly report for a session."""
    events = read_trace_events(session, trace_dir)
    if not events:
        typer.echo(f"No trace events found for session {session!r} in {trace_dir}.")
        raise typer.Exit(code=1)
    event = latest_context_event(events)
    if event is None:
        typer.echo(f"No context_built event found for session {session!r}.")
        raise typer.Exit(code=1)
    typer.echo(format_context_summary(event))


@trace_app.command("report")
def trace_report(
    session: str = typer.Option(
        DEFAULT_TRACE_SESSION,
        "--session",
        "-s",
        help="Trace session key, for example cli:default.",
    ),
    trace_dir: Path = typer.Option(
        Path("data/traces"),
        "--trace-dir",
        help="Directory containing JSONL trace files.",
    ),
    output: Path = typer.Option(
        Path("data/traces/report.html"),
        "--output",
        "-o",
        help="HTML report output path.",
    ),
) -> None:
    """Generate a static HTML report for trace inspection."""
    path = write_trace_report(
        output_path=output,
        trace_root=trace_dir,
        session_key=session,
    )
    typer.echo(f"Trace report written to {path}")


@trace_app.command("viewer")
def trace_viewer(
    output: Path = typer.Option(
        Path("data/traces/viewer.html"),
        "--output",
        "-o",
        help="Interactive HTML viewer output path.",
    ),
) -> None:
    """Generate an interactive local HTML viewer that can load JSONL trace files."""
    path = write_trace_viewer(output)
    typer.echo(f"Trace viewer written to {path}")


@trace_app.command("skills")
def trace_skills(
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        help="Number of recent skill events to show.",
    ),
    trace_dir: Path = typer.Option(
        Path("data/traces"),
        "--trace-dir",
        help="Directory containing JSONL trace files.",
    ),
) -> None:
    """Show recent runtime skill events such as skill_loaded and active_skill_set."""
    events = read_trace_events(SKILLS_TRACE_SESSION, trace_dir)
    if not events:
        typer.echo(f"No skill trace events found in {trace_dir}.")
        raise typer.Exit(code=1)
    typer.echo(format_trace_events(events, limit=limit))


@trace_app.command("startup")
def trace_startup(
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        help="Number of recent startup events to show.",
    ),
    trace_dir: Path = typer.Option(
        Path("data/traces"),
        "--trace-dir",
        help="Directory containing JSONL trace files.",
    ),
) -> None:
    """Show recent runtime startup events such as MCP server registration."""
    events = read_trace_events(STARTUP_TRACE_SESSION, trace_dir)
    if not events:
        typer.echo(f"No startup trace events found in {trace_dir}.")
        raise typer.Exit(code=1)
    typer.echo(format_trace_events(events, limit=limit))


app.add_typer(trace_app, name="trace")
