"""Tools for loading full local skill instructions."""

from typing import Any

from myagent.skills import SkillRegistry
from myagent.tools.base import Tool


class SkillGetTool(Tool):
    """Load the full SKILL.md for one discovered skill."""

    def __init__(self, registry: SkillRegistry) -> None:
        self.registry = registry

    @property
    def name(self) -> str:
        return "skill_get"

    @property
    def description(self) -> str:
        return (
            "Load the full instructions for one local skill by skill_id. Use this "
            "when a listed skill appears relevant and its complete workflow is needed."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "skill_id": {
                    "type": "string",
                    "description": "Skill id from the Available Skills section.",
                }
            },
            "required": ["skill_id"],
        }

    async def execute(self, skill_id: str, **_: Any) -> str:
        skill = self.registry.get(skill_id)
        if skill is None:
            available = ", ".join(skill.id for skill in self.registry.list_skills())
            return f"Skill '{skill_id}' not found. Available skills: {available}"
        content = self.registry.read_skill(skill.id)
        if content is None:
            return f"Skill '{skill_id}' not found."
        allowed = ", ".join(skill.allowed_tools) if skill.allowed_tools else "not specified"
        return (
            f"Skill: {skill.id}\n"
            f"Name: {skill.name}\n"
            f"Description: {skill.description}\n"
            f"Path: {skill.path.as_posix()}\n"
            f"Allowed Tools: {allowed}\n\n"
            f"{content}"
        )
