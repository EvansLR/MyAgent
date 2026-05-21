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

from myagent.approval import ApprovalRoute
from myagent.bus import InboundMessage, MessageBus, OutboundMessage
from myagent.channels import ChannelManager, FeishuChannel
from myagent.cli.runtime import create_agent_runtime
from myagent.config import Settings

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
    runtime = await create_agent_runtime(
        settings,
        bus,
        workspace_root=workspace_root,
        approval_callback=_make_cli_approval_callback(bus),
        start_cron=False,
    )
    agent_task = asyncio.create_task(runtime.agent.run_until_stopped())
    try:
        await run_chat(bus)
    finally:
        runtime.agent.stop()
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass
        for client in runtime.mcp_clients:
            await client.close()


async def run_gateway(
    settings: Settings | None = None,
    config_path: str | None = None,
) -> None:
    """Run gateway: AgentLoop + Channels + CronService."""
    settings = settings or Settings.from_sources(config_path)
    bus = MessageBus()
    workspace_root = Path.cwd()
    runtime = await create_agent_runtime(
        settings,
        bus,
        workspace_root=workspace_root,
        approval_callback=_make_cli_approval_callback(bus),
        start_cron=True,
    )

    # ChannelManager
    channel_manager = ChannelManager(bus)
    for name, cfg in settings.channels.items():
        if not cfg.get("enabled", True):
            continue
        if name == "feishu":
            channel_manager.register(FeishuChannel(cfg, bus))

    agent_task = asyncio.create_task(runtime.agent.run_until_stopped())
    channel_task = asyncio.create_task(channel_manager.start_all())

    typer.echo("MyAgent gateway started.")
    try:
        await agent_task
    except asyncio.CancelledError:
        pass
    finally:
        channel_task.cancel()
        try:
            await channel_task
        except asyncio.CancelledError:
            pass
        await channel_manager.stop_all()
        runtime.agent.stop()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass
        for client in runtime.mcp_clients:
            await client.close()


def _make_cli_approval_callback(bus: MessageBus):
    async def approve(prompt: str, route: ApprovalRoute | None = None) -> bool:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()
        channel = route.channel if route is not None else "cli"
        chat_id = route.chat_id if route is not None else DEFAULT_CHAT_ID
        await bus.publish_outbound(
            OutboundMessage(
                channel=channel,
                chat_id=chat_id,
                content=prompt,
                metadata={
                    "kind": "approval_request",
                    "future": future,
                },
            )
        )
        return await future

    return approve


app = typer.Typer(
    name="myagent",
    help="MyAgent - lightweight ReAct agent runtime.",
    no_args_is_help=False,
)


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


@app.command("gateway")
def gateway(
    config: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to a myagent JSON config file.",
    ),
) -> None:
    """Run the gateway (AgentLoop + Channels + Cron)."""
    asyncio.run(run_gateway(config_path=config))
