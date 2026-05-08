"""Skill entry data structures."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SkillEntry:
    """One local prompt skill discovered from SKILL.md."""

    id: str
    name: str
    description: str
    path: Path
    allowed_tools: tuple[str, ...] = ()
