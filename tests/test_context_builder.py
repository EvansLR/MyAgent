from myagent.agent import ContextBuilder
from myagent.bus import InboundMessage


def make_message(content: str = "hello") -> InboundMessage:
    return InboundMessage(
        channel="cli",
        sender_id="local-user",
        chat_id="default",
        content=content,
    )


def test_context_builder_builds_system_prompt() -> None:
    builder = ContextBuilder()

    prompt = builder.build_system_prompt()

    assert "# Identity" in prompt
    assert "MyAgent" in prompt


def test_context_builder_builds_messages_with_history() -> None:
    builder = ContextBuilder(identity="Test identity.")
    history = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
    ]

    messages = builder.build_messages(make_message("third"), history)

    assert messages == [
        {"role": "system", "content": "# Identity\n\nTest identity."},
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
        {"role": "user", "content": "third"},
    ]
