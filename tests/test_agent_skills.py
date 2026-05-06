from pathlib import Path
import shutil

from myagent.agent import AgentLoop
from myagent.bus import InboundMessage, MessageBus
from myagent.providers.base import ProviderResponse
from myagent.skills import SkillRegistry


def make_message(content: str = "hello") -> InboundMessage:
    return InboundMessage(
        channel="cli",
        sender_id="local-user",
        chat_id="default",
        content=content,
    )


def make_workspace(name: str) -> Path:
    root = Path(".test-workspaces") / "agent-skills" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def write_skill(root: Path, skill_id: str, description: str) -> None:
    path = root / skill_id / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "\n".join(
            [
                "---",
                f"name: {skill_id}",
                f"description: {description}",
                "---",
                "",
                f"# {skill_id}",
            ]
        ),
        encoding="utf-8",
    )


class CapturingProvider:
    def __init__(self) -> None:
        self.seen_messages = []

    async def generate(self, messages):
        self.seen_messages.append(messages)
        return "ok"

    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        self.seen_messages.append(messages)
        return ProviderResponse(content="ok")


async def test_agent_loop_injects_available_skills_into_context() -> None:
    root = make_workspace("default")
    write_skill(root, "interview-prep", "Help with interview preparation.")
    provider = CapturingProvider()
    bus = MessageBus()
    agent = AgentLoop(
        bus,
        provider=provider,
        skill_registry=SkillRegistry.from_directory(root),
    )

    await bus.publish_inbound(make_message("你现在有哪些 skills？"))
    await agent.process_next()

    system_prompt = provider.seen_messages[0][0]["content"]

    assert "# Available Skills" in system_prompt
    assert "interview-prep" in system_prompt
    assert "Help with interview preparation." in system_prompt
    assert "Path:" in system_prompt
