from pathlib import Path
import shutil

from myagent.agent import ContextBuilder
from myagent.bus import InboundMessage
from myagent.memory import JsonlMemoryStore, MemoryRecall
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


def test_context_builder_includes_recalled_memory() -> None:
    store = JsonlMemoryStore(make_workspace("memory") / "facts.jsonl")
    store.add("我正在准备 Java 后端面试。", "cli:default")
    builder = ContextBuilder(
        identity="Test identity.",
        memory_recall=MemoryRecall(store),
    )

    messages = builder.build_messages(make_message("Java 面试怎么准备？"))

    assert "# Memory" in messages[0]["content"]
    assert "我正在准备 Java 后端面试。" in messages[0]["content"]


def test_context_builder_includes_core_memory() -> None:
    builder = ContextBuilder(
        identity="Test identity.",
        core_memory_provider=lambda: "## User Profile\n\n- 用户偏好文档优先。",
    )

    messages = builder.build_messages(make_message("hello"))

    assert "# Core Memory" in messages[0]["content"]
    assert "用户偏好文档优先。" in messages[0]["content"]


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
