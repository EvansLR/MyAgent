from pathlib import Path
import shutil

import pytest

from myagent.workspace import WorkspaceLoader
from myagent.agent.context import ContextBuilder


def make_workspace(name: str) -> Path:
    root = Path(".test-workspaces") / "workspace" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def test_workspace_creates_directory_if_missing() -> None:
    root = Path(".test-workspaces") / "workspace" / "auto-create"
    if root.exists():
        shutil.rmtree(root)
    assert not root.exists()
    loader = WorkspaceLoader(root)
    assert root.exists()


def test_workspace_loads_existing_files() -> None:
    root = make_workspace("existing")
    (root / "AGENT.md").write_text("Be helpful.", encoding="utf-8")
    (root / "PERSONA.md").write_text("Concise.", encoding="utf-8")
    loader = WorkspaceLoader(root)

    assert loader.load_file("AGENT.md") == "Be helpful."
    assert loader.load_file("PERSONA.md") == "Concise."


def test_workspace_returns_empty_for_missing_files() -> None:
    root = make_workspace("missing")
    loader = WorkspaceLoader(root)

    assert loader.load_file("AGENT.md") == ""
    assert loader.load_file("PERSONA.md") == ""


def test_workspace_present_and_missing_files() -> None:
    root = make_workspace("present-missing")
    (root / "AGENT.md").write_text("x", encoding="utf-8")
    loader = WorkspaceLoader(root)

    assert loader.present_files() == ["AGENT.md"]
    assert "AGENT.md" not in loader.missing_files()
    assert "USER.md" in loader.missing_files()


def test_workspace_trace_data() -> None:
    root = make_workspace("trace")
    (root / "AGENT.md").write_text("x", encoding="utf-8")
    loader = WorkspaceLoader(root)

    data = loader.to_trace_data()
    assert data["workspace_root"] == str(root)
    assert "AGENT.md" in data["files_present"]
    assert "USER.md" in data["files_missing"]


def test_context_builder_includes_workspace_sections() -> None:
    root = make_workspace("context")
    (root / "AGENT.md").write_text("Always verify before acting.", encoding="utf-8")
    (root / "USER.md").write_text("Developer who prefers Python.", encoding="utf-8")
    loader = WorkspaceLoader(root)
    builder = ContextBuilder(workspace_provider=loader)

    sections = builder.build_sections()
    names = [s.name for s in sections]

    assert "Agent Principles" in names
    assert "User Profile" in names


def test_context_builder_skips_empty_workspace_files() -> None:
    root = make_workspace("empty")
    loader = WorkspaceLoader(root)
    builder = ContextBuilder(workspace_provider=loader)

    sections = builder.build_sections()
    names = [s.name for s in sections]

    assert "Agent Principles" not in names
    assert "Agent Persona" not in names
    assert "User Profile" not in names
