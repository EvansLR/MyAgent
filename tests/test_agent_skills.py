from pathlib import Path
import shutil

from myagent.agent import AgentLoop
from myagent.bus import InboundMessage, MessageBus
from myagent.providers.base import ProviderResponse, ToolCall
from myagent.skills import SkillRegistry
from myagent.tracing import JsonlTraceStore


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


class SkillGetProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, messages):
        return "fallback"

    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        self.calls += 1
        if self.calls == 1:
            return ProviderResponse(
                tool_calls=[
                    ToolCall(
                        id="skill-call-1",
                        name="skill_get",
                        arguments={"skill_id": "code-review"},
                    )
                ]
            )
        return ProviderResponse(content="loaded")


class SkillGetThenAnswerProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.seen_messages = []

    async def generate(self, messages):
        return "fallback"

    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        self.calls += 1
        self.seen_messages.append(messages)
        if self.calls == 1:
            return ProviderResponse(
                tool_calls=[
                    ToolCall(
                        id="skill-call-1",
                        name="skill_get",
                        arguments={"skill_id": "code-review"},
                    )
                ]
            )
        return ProviderResponse(content="loaded")


class SkillGetThenContinueProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.seen_messages = []

    async def generate(self, messages):
        return "fallback"

    async def generate_response(self, messages, tools=None) -> ProviderResponse:
        self.calls += 1
        self.seen_messages.append(messages)
        if self.calls == 1:
            return ProviderResponse(
                tool_calls=[
                    ToolCall(
                        id="skill-call-1",
                        name="skill_get",
                        arguments={"skill_id": "code-review"},
                    )
                ]
            )
        return ProviderResponse(content="continued with active skill")


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
    assert "Full Instructions: call skill_get" in system_prompt

    tool_names = [
        definition["function"]["name"]
        for definition in agent.tool_registry.get_definitions()
    ]
    assert "skill_get" in tool_names


async def test_agent_loop_traces_skill_get_usage() -> None:
    root = make_workspace("trace")
    write_skill(root, "code-review", "Review code changes.")
    provider = SkillGetProvider()
    bus = MessageBus()
    trace_store = JsonlTraceStore(root / "traces")
    agent = AgentLoop(
        bus,
        provider=provider,
        skill_registry=SkillRegistry.from_directory(root),
        trace_store=trace_store,
    )

    await bus.publish_inbound(make_message("Use code-review skill."))
    await agent.process_next()

    lines = (root / "traces" / "runtime_skills.jsonl").read_text(encoding="utf-8").splitlines()
    load_events = [
        line
        for line in lines
        if "skill_loaded" in line
    ]
    active_events = [
        line
        for line in lines
        if "active_skill_set" in line
    ]
    assert load_events
    assert active_events
    assert "code-review" in load_events[0]
    assert "code-review" in active_events[0]
    assert "loaded_by_skill_get" in active_events[0]


async def test_agent_loop_includes_active_skill_section_after_skill_get() -> None:
    root = make_workspace("active-skill-section")
    write_skill(root, "code-review", "Review code changes.")
    provider = SkillGetThenContinueProvider()
    bus = MessageBus()
    agent = AgentLoop(
        bus,
        provider=provider,
        skill_registry=SkillRegistry.from_directory(root),
    )

    await bus.publish_inbound(make_message("Use code-review and continue."))
    await agent.process_next()

    second_call_system_prompt = provider.seen_messages[1][0]["content"]
    assert "# Active Skills" in second_call_system_prompt
    assert "code-review: code-review" in second_call_system_prompt
    assert "reason: loaded_by_skill_get" in second_call_system_prompt
