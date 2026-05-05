"""Typer entrypoint for the local CLI channel."""

import asyncio
from dataclasses import dataclass

import typer

from myagent.agent import AgentLoop
from myagent.bus import InboundMessage, MessageBus

DEFAULT_SENDER_ID = "local-user"
DEFAULT_CHAT_ID = "default"
SUPPORTED_COMMANDS = {"/help", "/new", "/stop"}


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
    raise ValueError(f"Unsupported CLI command: {command}")


async def run_chat(
    bus: MessageBus,
    *,
    state: CliState | None = None,
    input_func=input,
    output_func=typer.echo,
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
        outbound = await bus.consume_outbound()
        output_func(f"MyAgent: {outbound.content}")


async def run_local_echo_chat() -> None:
    """Run CLI + MessageBus + AgentLoop with the temporary EchoProvider."""
    bus = MessageBus()
    agent = AgentLoop(bus)
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


app = typer.Typer(
    name="myagent",
    help="MyAgent - lightweight ReAct agent runtime.",
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def main() -> None:
    """Run the local CLI channel."""
    asyncio.run(run_local_echo_chat())
