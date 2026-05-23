from datetime import datetime, timezone
from pathlib import Path
import shutil

from myagent.agent import ContextBudget, ContextBuilder, format_runtime_environment
from myagent.bus import InboundMessage
from myagent.skills import SkillRegistry
from myagent.skills.entries import SkillEntry


def make_message(content: str = "hello") -> InboundMessage:
    return InboundMessage(
        channel="cli",
        sender_id="local-user",
        chat_id="default",
        content=content,
    )


def make_workspace(name: str) -> Path:
    root = Path(".test-workspaces") / "context-builder" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def test_context_builder_builds_system_message() -> None:
    builder = ContextBuilder()

    messages = builder.build_messages(make_message("hello"))
    prompt = messages[0]["content"]

    assert "# Identity" in prompt
    assert "MyAgent" in prompt


def test_context_budget_defaults_are_long_context_friendly() -> None:
    budget = ContextBudget()

    assert budget.max_prompt_tokens == 128_000
    assert budget.raw_history_token_limit == 128_000
    assert budget.raw_history_target_tokens == 80_000
    assert budget.summary_token_limit == 8_000
    assert budget.memory_token_limit == 16_000
    assert budget.raw_history_target_tokens < budget.raw_history_token_limit


def test_context_builder_builds_messages_with_history() -> None:
    builder = ContextBuilder(identity="Test identity.", delegation_policy=None)
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


def test_context_builder_includes_runtime_environment() -> None:
    workspace = make_workspace("runtime")
    builder = ContextBuilder(
        identity="Test identity.",
        runtime_environment=format_runtime_environment(
            workspace,
            now=datetime(2026, 5, 9, 10, 30, tzinfo=timezone.utc),
        ),
    )

    messages = builder.build_messages(make_message("hello"))

    assert "# Runtime Environment" in messages[0]["content"]
    assert str(workspace.resolve()) in messages[0]["content"]
    assert "Current date: 2026-05-09" in messages[0]["content"]
    assert "Resolve relative dates" in messages[0]["content"]
    assert "Do not invent absolute paths." in messages[0]["content"]


def test_context_builder_refreshes_runtime_environment_provider_each_build() -> None:
    values = iter(["time one", "time two"])
    builder = ContextBuilder(
        identity="Test identity.",
        runtime_environment_provider=lambda: next(values),
    )

    first = builder.build_messages(make_message("hello"))
    second = builder.build_messages(make_message("hello again"))

    assert "time one" in first[0]["content"]
    assert "time two" in second[0]["content"]


def test_context_builder_splits_always_and_now_memory() -> None:
    builder = ContextBuilder(
        identity="Test identity.",
        always_memory_provider=lambda: "- Stable preference.",
        now_memory_provider=lambda: "- Current project state.",
    )

    messages = builder.build_messages(make_message("hello"))
    system_prompt = messages[0]["content"]

    assert "# Always Memory" in system_prompt
    assert "Stable preference." in system_prompt
    assert "# Now Memory" in system_prompt
    assert "Current project state." in system_prompt
    assert "# Long-term Memory" not in system_prompt


def test_context_builder_includes_conversation_summary_section() -> None:
    builder = ContextBuilder(
        identity="Test identity.",
        conversation_summary_provider=lambda: "- Earlier decision: keep summary lightweight.",
    )

    messages = builder.build_messages(make_message("hello"))

    assert "# Conversation Summary" in messages[0]["content"]
    assert "Earlier decision" in messages[0]["content"]


def test_context_builder_omits_empty_conversation_summary() -> None:
    builder = ContextBuilder(
        identity="Test identity.",
        conversation_summary_provider=lambda: "   ",
    )

    messages = builder.build_messages(make_message("hello"))

    assert "# Conversation Summary" not in messages[0]["content"]


def test_context_builder_includes_available_skills() -> None:
    skill_registry = SkillRegistry(
        [
            SkillEntry(
                id="code-review",
                name="code-review",
                description="Review code changes.",
                path=Path("skills/code-review/SKILL.md"),
            )
        ]
    )
    builder = ContextBuilder(
        identity="Test identity.",
        skill_registry=skill_registry,
    )

    messages = builder.build_messages(make_message("what skills are available?"))

    assert "# Available Skills" in messages[0]["content"]
    assert "code-review" in messages[0]["content"]
    assert "call skill_get first" in messages[0]["content"]


def test_context_builder_omits_active_skills_when_none_active() -> None:
    builder = ContextBuilder(identity="Test identity.", active_skills_provider=lambda: "")

    messages = builder.build_messages(make_message("hello"))

    assert "# Active Skills" not in messages[0]["content"]


def test_context_builder_includes_compact_active_skills_section() -> None:
    builder = ContextBuilder(
        identity="Test identity.",
        active_skills_provider=lambda: "- frontend-design: Frontend Design\n  reason: loaded_by_skill_get",
    )

    messages = builder.build_messages(make_message("hello"))

    assert "# Active Skills" in messages[0]["content"]
    assert "frontend-design: Frontend Design" in messages[0]["content"]
    assert "reason: loaded_by_skill_get" in messages[0]["content"]


def test_context_builder_includes_delegation_policy_as_required_section() -> None:
    builder = ContextBuilder(identity="Test identity.")

    messages = builder.build_messages(make_message("research this"))

    assert "# Delegation Policy" in messages[0]["content"]
    assert "Use delegate_task proactively" in messages[0]["content"]
    assert "Do not require the user to explicitly ask for a subagent" in messages[0]["content"]


def test_context_builder_keeps_history_when_over_budget() -> None:
    builder = ContextBuilder(
        identity="ID",
        delegation_policy=None,
        budget=ContextBudget(
            max_prompt_tokens=30,
            chars_per_token=1,
        ),
    )
    history = [
        {"role": "user", "content": "old old old old"},
        {"role": "assistant", "content": "old reply old reply"},
        {"role": "user", "content": "recent"},
        {"role": "assistant", "content": "reply"},
    ]

    messages = builder.build_messages(make_message("now"), history)

    assert {"role": "user", "content": "old old old old"} in messages
    assert {"role": "assistant", "content": "old reply old reply"} in messages
    assert {"role": "user", "content": "recent"} in messages
    assert {"role": "assistant", "content": "reply"} in messages
