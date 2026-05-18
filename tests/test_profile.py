from pathlib import Path
import shutil

from myagent.agent.context import ContextBuilder
from myagent.profile import ProfileLoader


def make_profile(name: str) -> Path:
    root = Path(".test-workspaces") / "profile" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def test_profile_loader_does_not_create_directory_when_reading() -> None:
    root = Path(".test-workspaces") / "profile" / "auto-create"
    if root.exists():
        shutil.rmtree(root)
    assert not root.exists()
    loader = ProfileLoader(root)
    assert loader.load_file("AGENT.md") == ""
    assert not root.exists()


def test_profile_loads_existing_files() -> None:
    root = make_profile("existing")
    (root / "AGENT.md").write_text("Be helpful.", encoding="utf-8")
    (root / "TOOLS.md").write_text("Use tools carefully.", encoding="utf-8")
    loader = ProfileLoader(root)

    assert loader.load_file("AGENT.md") == "Be helpful."
    assert loader.load_file("TOOLS.md") == "Use tools carefully."


def test_profile_returns_empty_for_missing_files() -> None:
    root = make_profile("missing")
    loader = ProfileLoader(root)

    assert loader.load_file("AGENT.md") == ""
    assert loader.load_file("PERSONA.md") == ""


def test_default_profile_loader_reads_only_profile_directory(monkeypatch) -> None:
    home = make_profile("home")
    profile = home / ".myagent" / "profile"
    legacy_workspace = home / ".myagent" / "workspace"
    profile.mkdir(parents=True)
    legacy_workspace.mkdir(parents=True)
    (profile / "AGENT.md").write_text("New profile.", encoding="utf-8")
    (legacy_workspace / "AGENT.md").write_text("Legacy profile.", encoding="utf-8")
    monkeypatch.setattr(Path, "home", lambda: home)

    loader = ProfileLoader()

    assert loader.root == home / ".myagent" / "profile"
    assert loader.load_file("AGENT.md") == "New profile."


def test_profile_does_not_fallback_to_workspace(monkeypatch) -> None:
    home = make_profile("no-fallback")
    legacy_workspace = home / ".myagent" / "workspace"
    legacy_workspace.mkdir(parents=True)
    (legacy_workspace / "AGENT.md").write_text("Legacy profile.", encoding="utf-8")
    monkeypatch.setattr(Path, "home", lambda: home)

    loader = ProfileLoader()

    assert loader.load_file("AGENT.md") == ""


def test_profile_present_and_missing_files() -> None:
    root = make_profile("present-missing")
    (root / "AGENT.md").write_text("x", encoding="utf-8")
    loader = ProfileLoader(root)

    assert loader.present_files() == ["AGENT.md"]
    assert "AGENT.md" not in loader.missing_files()
    assert "USER.md" in loader.missing_files()


def test_profile_trace_data() -> None:
    root = make_profile("trace")
    (root / "AGENT.md").write_text("x", encoding="utf-8")
    loader = ProfileLoader(root)

    data = loader.to_trace_data()
    assert data["profile_root"] == str(root)
    assert "legacy_profile_root" not in data
    assert "AGENT.md" in data["files_present"]
    assert "USER.md" in data["files_missing"]


def test_context_builder_includes_profile_sections() -> None:
    root = make_profile("context")
    (root / "AGENT.md").write_text("Always verify before acting.", encoding="utf-8")
    (root / "USER.md").write_text("Developer who prefers Python.", encoding="utf-8")
    loader = ProfileLoader(root)
    builder = ContextBuilder(profile_provider=loader)

    sections = builder.build_sections()
    names = [s.name for s in sections]

    assert "Agent Instructions" in names
    assert "User Profile" in names


def test_context_builder_skips_empty_profile_files() -> None:
    root = make_profile("empty")
    loader = ProfileLoader(root)
    builder = ContextBuilder(profile_provider=loader)

    sections = builder.build_sections()
    names = [s.name for s in sections]

    assert "Agent Instructions" not in names
    assert "Agent Persona" not in names
    assert "User Profile" not in names
