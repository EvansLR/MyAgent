import pytest

from myagent.cli.commands import (
    CliState,
    handle_cli_command,
    make_help_text,
    make_inbound_message,
    parse_cli_command,
    run_chat,
)
from myagent.bus import MessageBus, OutboundMessage


def test_parse_help_command() -> None:
    assert parse_cli_command("/help") == "help"


def test_parse_new_command() -> None:
    assert parse_cli_command("/new") == "new"


def test_parse_stop_command() -> None:
    assert parse_cli_command("/stop") == "stop"


def test_parse_plain_text_as_message() -> None:
    assert parse_cli_command("hello") == "message"


def test_unknown_slash_command_is_message() -> None:
    assert parse_cli_command("/unknown") == "message"


def test_make_inbound_message_uses_current_cli_state() -> None:
    state = CliState(chat_id="session-1")

    msg = make_inbound_message("hello", state)

    assert msg.channel == "cli"
    assert msg.sender_id == "local-user"
    assert msg.chat_id == "session-1"
    assert msg.content == "hello"
    assert msg.session_key == "cli:session-1"


def test_new_session_changes_chat_id() -> None:
    state = CliState()

    output = handle_cli_command("new", state)

    assert state.chat_id == "session-1"
    assert state.session_index == 1
    assert output == "Started a new session: cli:session-1"


def test_stop_command_marks_state_not_running() -> None:
    state = CliState()

    output = handle_cli_command("stop", state)

    assert state.running is False
    assert output == "Stopping MyAgent CLI."


def test_help_text_mentions_supported_commands() -> None:
    help_text = make_help_text()

    assert "/help" in help_text
    assert "/new" in help_text
    assert "/stop" in help_text


def test_handle_unknown_command_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported CLI command"):
        handle_cli_command("missing", CliState())


async def test_run_chat_handles_help_and_stop() -> None:
    bus = MessageBus()
    inputs = iter(["/help", "/stop"])
    outputs: list[str] = []

    await run_chat(
        bus,
        input_func=lambda _prompt: next(inputs),
        output_func=outputs.append,
    )

    assert any("/help" in output for output in outputs)
    assert outputs[-1] == "Stopping MyAgent CLI."


async def test_run_chat_sends_message_and_prints_outbound() -> None:
    bus = MessageBus()
    inputs = iter(["hello", "/stop"])
    outputs: list[str] = []

    async def publish_reply() -> None:
        inbound = await bus.consume_inbound()
        await bus.publish_outbound(
            OutboundMessage(
                channel=inbound.channel,
                chat_id=inbound.chat_id,
                content=f"Echo: {inbound.content}",
            )
        )

    import asyncio

    reply_task = asyncio.create_task(publish_reply())
    await run_chat(
        bus,
        input_func=lambda _prompt: next(inputs),
        output_func=outputs.append,
    )
    await reply_task

    assert "MyAgent: Echo: hello" in outputs


async def test_run_chat_prints_status_before_final_reply() -> None:
    bus = MessageBus()
    inputs = iter(["inspect files", "/stop"])
    outputs: list[str] = []

    async def publish_reply() -> None:
        inbound = await bus.consume_inbound()
        await bus.publish_outbound(
            OutboundMessage(
                channel=inbound.channel,
                chat_id=inbound.chat_id,
                content="Using tool: list_dir path=docs/modules",
                metadata={"kind": "status"},
            )
        )
        await bus.publish_outbound(
            OutboundMessage(
                channel=inbound.channel,
                chat_id=inbound.chat_id,
                content="Final summary",
            )
        )

    import asyncio

    reply_task = asyncio.create_task(publish_reply())
    await run_chat(
        bus,
        input_func=lambda _prompt: next(inputs),
        output_func=outputs.append,
    )
    await reply_task

    assert "MyAgent: Using tool: list_dir path=docs/modules" in outputs
    assert "MyAgent: Final summary" in outputs
    assert outputs.index("MyAgent: Using tool: list_dir path=docs/modules") < outputs.index(
        "MyAgent: Final summary"
    )
