from pathlib import Path
import shutil

from myagent.skills import SkillLoader, SkillRegistry


def make_workspace(name: str) -> Path:
    root = Path(".test-workspaces") / "skills" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def write_skill(root: Path, skill_id: str, content: str) -> Path:
    path = root / skill_id / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_skill_loader_returns_empty_when_directory_missing() -> None:
    root = make_workspace("missing") / "no-skills"

    assert SkillLoader(root).scan() == []


def test_skill_loader_reads_frontmatter_metadata() -> None:
    root = make_workspace("frontmatter")
    write_skill(
        root,
        "code-review",
        "\n".join(
            [
                "---",
                "name: code-review",
                "description: Review code changes.",
                "---",
                "",
                "# Code Review",
            ]
        ),
    )

    skills = SkillLoader(root).scan()

    assert skills[0].id == "code-review"
    assert skills[0].name == "code-review"
    assert skills[0].description == "Review code changes."
    assert skills[0].path.as_posix().endswith("code-review/SKILL.md")


def test_skill_loader_falls_back_to_heading_and_description_section() -> None:
    root = make_workspace("markdown")
    write_skill(
        root,
        "interview",
        "\n".join(
            [
                "# Interview Skill",
                "",
                "## Description",
                "",
                "Help with interview preparation.",
                "",
                "## Instructions",
                "",
                "- Be practical.",
            ]
        ),
    )

    skill = SkillLoader(root).scan()[0]

    assert skill.name == "Interview Skill"
    assert skill.description == "Help with interview preparation."


def test_skill_registry_formats_skills_for_context() -> None:
    root = make_workspace("registry")
    write_skill(
        root,
        "commit-message",
        "\n".join(
            [
                "---",
                "name: commit-message",
                "description: Generate concise Git commit messages.",
                "---",
            ]
        ),
    )

    content = SkillRegistry.from_directory(root).format_for_context()

    assert "- commit-message" in content
    assert "Name: commit-message" in content
    assert "Description: Generate concise Git commit messages." in content
    assert "Path:" in content
