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

    def format_for_context(self) -> str:
        """Format skills as a compact system prompt section."""
        if not self._skills:
            return ""
        lines: list[str] = []
        for skill in self._skills:
            lines.extend(
                [
                    f"- {skill.id}",
                    f"  Name: {skill.name}",
                    f"  Description: {skill.description}",
                    f"  Path: {skill.path.as_posix()}",
                ]
            )
        return "\n".join(lines)
