"""Task-oriented subagent runner exposed through a delegation tool."""

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from myagent.agent.context.types import Message
from myagent.agent.runtime.messages import assistant_tool_call_message, tool_result_message
from myagent.providers.base import BaseProvider
from myagent.tools.base import Tool
from myagent.tools.registry import ToolRegistry


DEFAULT_SUBAGENT_PROFILE = "researcher"
MAX_SUBAGENT_ITERATIONS = 4


@dataclass(frozen=True, slots=True)
class SubAgentProfile:
    """Small prompt profile for a delegated task."""

    name: str
    description: str
    instructions: str
    allowed_tools: tuple[str, ...]
    max_iterations: int = MAX_SUBAGENT_ITERATIONS


PROFILES = {
    "researcher": SubAgentProfile(
        name="researcher",
        description="Read workspace files, search the web, and summarize concrete findings.",
        instructions=(
            "You are a focused researcher subagent for MyAgent. Your job is to "
            "inspect the given workspace context and public web sources with read-only "
            "tools, then return a concise, evidence-based summary. Do not chat with "
            "the user. Do not claim to edit files. If evidence is missing, say what "
            "you could not verify."
        ),
        allowed_tools=("list_dir", "read_file", "web_search", "web_fetch"),
    ),
    "reviewer": SubAgentProfile(
        name="reviewer",
        description="Review code or documents for risks, gaps, and next steps.",
        instructions=(
            "You are a focused reviewer subagent for MyAgent. Look for concrete "
            "risks, missing tests, confusing documentation, and implementation gaps. "
            "Return findings with file references when available."
        ),
        allowed_tools=("list_dir", "read_file"),
    ),
    "interviewer": SubAgentProfile(
        name="interviewer",
        description="Prepare interview-oriented explanations and follow-up questions.",
        instructions=(
            "You are a focused interview-prep subagent for MyAgent. Explain topics "
            "in a way a graduate student can use during technical interviews. Keep "
            "answers structured and practical."
        ),
        allowed_tools=("web_search", "web_fetch"),
    ),
}


class SubAgentRunner:
    """Run one bounded delegated task with a restricted tool registry."""

    def __init__(
        self,
        provider: BaseProvider,
        tool_registry: ToolRegistry,
        max_iterations: int = MAX_SUBAGENT_ITERATIONS,
    ) -> None:
        self.provider = provider
        self.tool_registry = tool_registry
        self.max_iterations = max_iterations

    async def run(
        self,
        task: str,
        agent_type: str = DEFAULT_SUBAGENT_PROFILE,
        context: str = "",
    ) -> str:
        """Run one delegated task and return the subagent's final answer."""
        profile = PROFILES.get(agent_type, PROFILES[DEFAULT_SUBAGENT_PROFILE])
        messages = _build_subagent_messages(profile, task, context)
        tools = self.tool_registry.get_definitions()

        if not hasattr(self.provider, "generate_response") or not tools:
            return await self.provider.generate(messages)

        working_messages = list(messages)
        for _ in range(self.max_iterations):
            response = await self.provider.generate_response(working_messages, tools=tools)
            if not response.tool_calls:
                return response.content

            working_messages.append(assistant_tool_call_message(response))
            for tool_call in response.tool_calls:
                result = await self.tool_registry.execute(tool_call.name, tool_call.arguments)
                working_messages.append(tool_result_message(tool_call, result))

        return "SubAgent reached its tool iteration limit before producing a final answer."


class DelegateTaskTool(Tool):
    """Tool that lets the main agent delegate one bounded task."""

    def __init__(
        self,
        provider: BaseProvider,
        parent_registry: ToolRegistry,
        max_iterations: int = MAX_SUBAGENT_ITERATIONS,
    ) -> None:
        self.provider = provider
        self.parent_registry = parent_registry
        self.max_iterations = max_iterations

    @property
    def name(self) -> str:
        return "delegate_task"

    @property
    def description(self) -> str:
        return (
            "Delegate a bounded read-only task to a focused subagent. Useful for "
            "inspecting files, summarizing docs, reviewing code, or preparing "
            "interview explanations while the main agent keeps final control."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Specific task for the subagent to complete.",
                },
                "agent_type": {
                    "type": "string",
                    "description": "Subagent profile: researcher, reviewer, or interviewer.",
                },
                "context": {
                    "type": "string",
                    "description": "Optional background context to pass to the subagent.",
                },
                "reason": {
                    "type": "string",
                    "description": "Brief reason why the main agent is delegating this task.",
                },
            },
            "required": ["task"],
        }

    async def execute(
        self,
        task: str,
        agent_type: str = DEFAULT_SUBAGENT_PROFILE,
        context: str = "",
        reason: str = "",
        active_skill_context: str = "",
        **_: Any,
    ) -> str:
        profile = get_subagent_profile(agent_type)
        child_registry = create_subagent_registry(
            self.parent_registry,
            profile.allowed_tools,
        )
        task_id = uuid4().hex[:8]
        runner = SubAgentRunner(
            provider=self.provider,
            tool_registry=child_registry,
            max_iterations=profile.max_iterations or self.max_iterations,
        )
        merged_context = _merge_context(context, active_skill_context)
        result = await runner.run(task=task, agent_type=profile.name, context=merged_context)
        return _format_subagent_result(profile.name, task, result, task_id)


def get_subagent_profile(agent_type: str = DEFAULT_SUBAGENT_PROFILE) -> SubAgentProfile:
    """Return a known profile, falling back to the default researcher."""
    return PROFILES.get(agent_type, PROFILES[DEFAULT_SUBAGENT_PROFILE])


def create_subagent_registry(
    parent_registry: ToolRegistry,
    allowed_tools: tuple[str, ...] | None = None,
) -> ToolRegistry:
    """Create a child registry from an explicit profile tool allowlist."""
    registry = ToolRegistry()
    for name in allowed_tools or get_subagent_profile().allowed_tools:
        tool = parent_registry.get(name)
        if tool is not None:
            registry.register(tool)
    return registry


def _build_subagent_messages(profile: SubAgentProfile, task: str, context: str) -> list[Message]:
    system_prompt = (
        f"# Role\n\n{profile.instructions}\n\n"
        "# Constraints\n\n"
        "- You are a subagent, not the main chat assistant.\n"
        "- Use only the tools provided to you.\n"
        "- Return the result to the main agent as concise text.\n"
        "- Do not delegate to another subagent.\n"
    )
    user_prompt = f"Task:\n{task.strip()}"
    if context.strip():
        user_prompt += f"\n\nContext:\n{context.strip()}"
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _format_subagent_result(
    agent_type: str,
    task: str,
    result: str,
    task_id: str | None = None,
) -> str:
    display_task_id = task_id or uuid4().hex[:8]
    return (
        f"SubAgent task {display_task_id}\n"
        f"profile: {agent_type or DEFAULT_SUBAGENT_PROFILE}\n"
        f"task: {task}\n\n"
        f"{result}"
    )


def _merge_context(context: str, active_skill_context: str) -> str:
    parts = [part.strip() for part in (context, active_skill_context) if part.strip()]
    return "\n\n".join(parts)


