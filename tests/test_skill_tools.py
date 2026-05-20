from pathlib import Path
import shutil

from myagent.skills import SkillRegistry
from myagent.tools.skills import SkillGetTool


def make_workspace(name: str) -> Path:
    root = Path(".test-workspaces") / "skill-tools" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def write_skill(root: Path, skill_id: str, content: str) -> None:
    path = root / skill_id / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")


async def test_skill_get_tool_loads_full_skill_content() -> None:
    root = make_workspace("get")
    write_skill(
        root,
        "code-review",
        "\n".join(
            [
                "---",
                "name: code-review",
                "description: Review code changes.",
                "allowed-tools: read_file, list_dir",
                "---",
                "",
                "# Code Review",
                "",
                "Use a review-first output shape.",
            ]
        ),
    )
    registry = SkillRegistry.from_directory(root)

    result = await SkillGetTool(registry).execute("code-review")

    assert "Skill: code-review" in result
    assert "Allowed Tools: read_file, list_dir" in result
    assert "Use a review-first output shape." in result


async def test_skill_get_tool_notifies_active_skill_callback() -> None:
    root = make_workspace("active-skill")
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
    registry = SkillRegistry.from_directory(root)
    active_skills: list[dict[str, object]] = []

    result = await SkillGetTool(
        registry,
        active_skill_callback=active_skills.append,
    ).execute("code-review")

    assert "Skill: code-review" in result
    assert active_skills == [
        {
            "skill_id": "code-review",
            "name": "code-review",
            "scope": "turn",
            "reason": "loaded_by_skill_get",
        },
    ]


async def test_skill_get_tool_reports_missing_skill() -> None:
    registry = SkillRegistry([])

    result = await SkillGetTool(registry).execute("missing")

    assert "Skill 'missing' not found" in result
