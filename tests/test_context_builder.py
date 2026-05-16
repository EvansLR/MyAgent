from pathlib import Path
import shutil
from datetime import datetime, timezone

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


def test_context_builder_builds_system_prompt() -> None:
    builder = ContextBuilder()

    prompt = builder.build_system_prompt()

    assert "# Identity" in prompt
    assert "MyAgent" in prompt


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

    messages, report = builder.build_messages_with_report(make_message("hello"))

    assert "# Runtime Environment" in messages[0]["content"]
    assert str(workspace.resolve()) in messages[0]["content"]
    assert "Current date: 2026-05-09" in messages[0]["content"]
    assert "Resolve relative dates" in messages[0]["content"]
    assert "Do not invent absolute paths." in messages[0]["content"]
    sections = {section.name: section for section in report.sections}
    assert sections["Runtime Environment"].tier == "protected"
    assert sections["Runtime Environment"].source == "runtime:environment"


def test_context_builder_includes_core_memory() -> None:
    builder = ContextBuilder(
        identity="Test identity.",
        core_memory_provider=lambda: "## Profile\n\n- 用户偏好文档优先。",
    )

    messages = builder.build_messages(make_message("hello"))

    assert "# Long-term Memory" in messages[0]["content"]
    assert "用户偏好文档优先。" in messages[0]["content"]


def test_context_builder_reports_sections_and_core_memory_tier() -> None:
    builder = ContextBuilder(
        identity="Test identity.",
        core_memory_provider=lambda: "## Profile\n\n- 用户名字是 lin。",
    )

    messages, report = builder.build_messages_with_report(make_message("hello"))

    assert messages[0]["role"] == "system"
    sections = {section.name: section for section in report.sections}
    assert sections["Identity"].tier == "protected"
    assert sections["Identity"].source == "identity"
    assert sections["Long-term Memory"].tier == "high"
    assert sections["Long-term Memory"].source == "memory:core"
    assert report.total_chars > 0
    assert report.estimated_tokens > 0


def test_context_builder_trims_history_by_budget() -> None:
    builder = ContextBuilder(
        identity="Test identity.",
        delegation_policy=None,
        budget=ContextBudget(max_history_messages=2),
    )
    history = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "second"},
        {"role": "user", "content": "third"},
        {"role": "assistant", "content": "fourth"},
    ]

    messages, report = builder.build_messages_with_report(make_message("fifth"), history)

    assert messages == [
        {"role": "system", "content": "# Identity\n\nTest identity."},
        {"role": "user", "content": "third"},
        {"role": "assistant", "content": "fourth"},
        {"role": "user", "content": "fifth"},
    ]
    assert report.history.total_messages == 4
    assert report.history.included_messages == 2
    assert report.history.dropped_messages == 2
    assert report.warnings == ["history_trimmed"]


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

    messages = builder.build_messages(make_message("你有哪些 skills？"))

    assert "# Available Skills" in messages[0]["content"]
    assert "code-review" in messages[0]["content"]
    assert "skills/code-review/SKILL.md" in messages[0]["content"]


def test_context_builder_omits_active_skills_when_none_active() -> None:
    builder = ContextBuilder(identity="Test identity.", active_skills_provider=lambda: "")

    messages = builder.build_messages(make_message("hello"))

    assert "# Active Skills" not in messages[0]["content"]


def test_context_builder_includes_compact_active_skills_section() -> None:
    builder = ContextBuilder(
        identity="Test identity.",
        active_skills_provider=lambda: "- frontend-design: Frontend Design\n  reason: loaded_by_skill_get",
    )

    messages, report = builder.build_messages_with_report(make_message("hello"))

    assert "# Active Skills" in messages[0]["content"]
    assert "frontend-design: Frontend Design" in messages[0]["content"]
    assert "reason: loaded_by_skill_get" in messages[0]["content"]
    sections = {section.name: section for section in report.sections}
    assert sections["Active Skills"].tier == "medium"
    assert sections["Active Skills"].source == "skills:active"


def test_context_builder_includes_delegation_policy_as_protected_section() -> None:
    builder = ContextBuilder(identity="Test identity.")

    messages, report = builder.build_messages_with_report(make_message("research this"))

    assert "# Delegation Policy" in messages[0]["content"]
    assert "Use delegate_task proactively" in messages[0]["content"]
    assert "Do not require the user to explicitly ask for a subagent" in messages[0]["content"]
    sections = {section.name: section for section in report.sections}
    assert sections["Delegation Policy"].tier == "protected"
    assert sections["Delegation Policy"].source == "agent:delegation_policy"
