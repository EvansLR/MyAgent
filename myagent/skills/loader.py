"""Load local SKILL.md files."""

from pathlib import Path

from myagent.skills.entries import SkillEntry


class SkillLoader:
    """Scan a skills directory and parse lightweight skill metadata."""

    def __init__(self, root: str | Path = "skills") -> None:
        self.root = Path(root)

    def scan(self) -> list[SkillEntry]:
        """Return all skills under root/*/SKILL.md."""
        if not self.root.exists():
            return []
        skill_files = sorted(self.root.glob("*/SKILL.md"))
        return [self.load_skill(path) for path in skill_files]

    def load_skill(self, path: str | Path) -> SkillEntry:
        """Load one skill file."""
        skill_path = Path(path)
        text = skill_path.read_text(encoding="utf-8")
        frontmatter, body = _split_frontmatter(text)
        metadata = _parse_frontmatter(frontmatter)
        skill_id = skill_path.parent.name
        name = metadata.get("name") or _first_heading(body) or skill_id
        description = metadata.get("description") or _description_section(body) or _fallback_summary(body)
        allowed_tools = _parse_allowed_tools(metadata.get("allowed-tools", ""))
        return SkillEntry(
            id=skill_id,
            name=name,
            description=description,
            path=skill_path,
            allowed_tools=allowed_tools,
        )


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Split simple YAML frontmatter from markdown body."""
    if not text.startswith("---"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    return parts[1].strip(), parts[2].strip()


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Parse simple key: value metadata without requiring a YAML dependency."""
    metadata: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key in {"name", "description", "allowed-tools"} and value:
            metadata[key] = value
    return metadata


def _parse_allowed_tools(value: str) -> tuple[str, ...]:
    """Parse a comma-separated allowed-tools metadata value."""
    if not value:
        return ()
    return tuple(tool.strip() for tool in value.split(",") if tool.strip())


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("# "):
            return line.removeprefix("# ").strip()
    return None


def _description_section(text: str) -> str | None:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip().lower() != "## description":
            continue
        content: list[str] = []
        for section_line in lines[index + 1 :]:
            stripped = section_line.strip()
            if stripped.startswith("## "):
                break
            if stripped:
                content.append(stripped)
            elif content:
                break
        return " ".join(content) or None
    return None


def _fallback_summary(text: str) -> str:
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return " ".join(lines[:2])
