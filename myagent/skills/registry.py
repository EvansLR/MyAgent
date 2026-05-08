"""Skill registry for context injection."""

from pathlib import Path

from myagent.skills.entries import SkillEntry
from myagent.skills.loader import SkillLoader


class SkillRegistry:
    """Hold locally discovered skills and format them for model context."""

    def __init__(self, skills: list[SkillEntry] | None = None) -> None:
        self._skills = skills or []

    @classmethod
    def from_directory(cls, root: str | Path = "skills") -> "SkillRegistry":
        """Scan a skills directory."""
        return cls(SkillLoader(root).scan())

    def list_skills(self) -> list[SkillEntry]:
        """Return discovered skills."""
        return list(self._skills)

    def get(self, skill_id: str) -> SkillEntry | None:
        """Return one skill by id or name."""
        for skill in self._skills:
            if skill.id == skill_id or skill.name == skill_id:
                return skill
        return None

    def read_skill(self, skill_id: str) -> str | None:
        """Return the full SKILL.md content for one skill."""
        skill = self.get(skill_id)
        if skill is None:
            return None
        return skill.path.read_text(encoding="utf-8")

    def format_for_context(self) -> str:
        """Format skills as a compact system prompt section."""
        if not self._skills:
            return ""
        lines: list[str] = []
        for skill in self._skills:
            lines.extend(_format_skill(skill))
        return "\n".join(lines)


def _format_skill(skill: SkillEntry) -> list[str]:
    lines = [
        f"- {skill.id}",
        f"  Name: {skill.name}",
        f"  Description: {skill.description}",
        f"  Path: {skill.path.as_posix()}",
    ]
    if skill.allowed_tools:
        lines.append(f"  Allowed Tools: {', '.join(skill.allowed_tools)}")
    lines.append("  Full Instructions: call skill_get with this skill id when needed.")
    return lines
