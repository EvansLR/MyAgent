from pathlib import Path
import shutil

from myagent.tools import create_default_registry
from myagent.tools.filesystem import CopyFileTool, EditFileTool, ListDirTool, MoveFileTool, ReadFileTool, WriteFileTool


def make_workspace(name: str) -> Path:
    root = Path(".test-workspaces") / "filesystem-tools" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def make_external_root(workspace: Path, name: str) -> Path:
    root = workspace.parent / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir()
    return root


async def test_list_dir_lists_workspace_files() -> None:
    workspace = make_workspace("list")
    (workspace / "a.txt").write_text("hello", encoding="utf-8")
    (workspace / "folder").mkdir()
    tool = ListDirTool(workspace)

    result = await tool.execute(".")

    assert "a.txt" in result
    assert "folder/" in result


async def test_list_dir_supports_recursive() -> None:
    workspace = make_workspace("recursive")
    nested = workspace / "folder"
    nested.mkdir()
    (nested / "a.txt").write_text("hello", encoding="utf-8")
    tool = ListDirTool(workspace)

    result = await tool.execute(".", recursive=True)

    assert "folder/a.txt" in result.replace("\\", "/")


async def test_read_file_returns_numbered_lines() -> None:
    workspace = make_workspace("read")
    (workspace / "a.txt").write_text("one\ntwo\nthree", encoding="utf-8")
    tool = ReadFileTool(workspace)

    result = await tool.execute("a.txt")

    assert "1| one" in result
    assert "2| two" in result
    assert "End of file" in result


async def test_read_file_supports_offset_and_limit() -> None:
    workspace = make_workspace("read_offset")
    (workspace / "a.txt").write_text("one\ntwo\nthree", encoding="utf-8")
    tool = ReadFileTool(workspace)

    result = await tool.execute("a.txt", offset=2, limit=1)

    assert "2| two" in result
    assert "1| one" not in result
    assert "Use offset=3" in result


async def test_read_file_can_read_external_path_without_approval() -> None:
    workspace = make_workspace("read-outside")
    outside_root = make_external_root(workspace, "outside-read")
    outside = (outside_root / "outside-read.txt").resolve()
    outside.write_text("secret", encoding="utf-8")

    tool = ReadFileTool(workspace)

    result = await tool.execute(str(outside))

    assert "secret" in result


async def test_list_dir_can_list_external_path_without_approval() -> None:
    workspace = make_workspace("list-outside")
    outside_root = make_external_root(workspace, "outside-list")
    (outside_root / "note.txt").write_text("hello", encoding="utf-8")
    tool = ListDirTool(workspace)

    result = await tool.execute(str(outside_root.resolve()))

    assert "note.txt" in result


async def test_write_file_saves_text_inside_workspace() -> None:
    workspace = make_workspace("write")
    tool = WriteFileTool(workspace)

    result = await tool.execute("pages/club-promotion.html", "<h1>Hello</h1>")

    assert "Wrote" in result
    assert (workspace / "pages" / "club-promotion.html").read_text(encoding="utf-8") == "<h1>Hello</h1>"


async def test_write_file_requires_overwrite_for_existing_file() -> None:
    workspace = make_workspace("write-existing")
    target = workspace / "note.txt"
    target.write_text("old", encoding="utf-8")
    tool = WriteFileTool(workspace)

    result = await tool.execute("note.txt", "new")

    assert "already exists" in result
    assert target.read_text(encoding="utf-8") == "old"


async def test_write_file_can_overwrite_existing_file() -> None:
    workspace = make_workspace("write-overwrite")
    target = workspace / "note.txt"
    target.write_text("old", encoding="utf-8")
    tool = WriteFileTool(workspace)

    result = await tool.execute("note.txt", "new", overwrite=True)

    assert "Wrote" in result
    assert target.read_text(encoding="utf-8") == "new"


async def test_write_file_can_write_allowed_external_root() -> None:
    workspace = make_workspace("write-outside")
    allowed_root = make_external_root(workspace, "allowed-write")
    outside = (allowed_root / "note.txt").resolve()

    tool = WriteFileTool(workspace, allowed_roots=[allowed_root])

    result = await tool.execute(str(outside), "hello")

    assert "Wrote" in result
    assert outside.read_text(encoding="utf-8") == "hello"


async def test_edit_file_replaces_unique_text() -> None:
    workspace = make_workspace("edit")
    target = workspace / "note.txt"
    target.write_text("hello old world", encoding="utf-8")
    tool = EditFileTool(workspace)

    result = await tool.execute("note.txt", "old", "new")

    assert "Edited note.txt" in result
    assert target.read_text(encoding="utf-8") == "hello new world"


async def test_edit_file_requires_existing_old_text() -> None:
    workspace = make_workspace("edit-missing")
    target = workspace / "note.txt"
    target.write_text("hello world", encoding="utf-8")
    tool = EditFileTool(workspace)

    result = await tool.execute("note.txt", "missing", "new")

    assert "old_text was not found" in result
    assert target.read_text(encoding="utf-8") == "hello world"


async def test_edit_file_rejects_ambiguous_text_by_default() -> None:
    workspace = make_workspace("edit-ambiguous")
    target = workspace / "note.txt"
    target.write_text("apple apple", encoding="utf-8")
    tool = EditFileTool(workspace)

    result = await tool.execute("note.txt", "apple", "orange")

    assert "matched 2 occurrences" in result
    assert target.read_text(encoding="utf-8") == "apple apple"


async def test_edit_file_can_replace_all_occurrences() -> None:
    workspace = make_workspace("edit-all")
    target = workspace / "note.txt"
    target.write_text("apple apple", encoding="utf-8")
    tool = EditFileTool(workspace)

    result = await tool.execute("note.txt", "apple", "orange", replace_all=True)

    assert "replaced 2 occurrence" in result
    assert target.read_text(encoding="utf-8") == "orange orange"


async def test_edit_file_rejects_empty_old_text() -> None:
    workspace = make_workspace("edit-empty")
    target = workspace / "note.txt"
    target.write_text("hello", encoding="utf-8")
    tool = EditFileTool(workspace)

    result = await tool.execute("note.txt", "", "new")

    assert "old_text must not be empty" in result
    assert target.read_text(encoding="utf-8") == "hello"


async def test_edit_file_can_edit_allowed_external_root() -> None:
    workspace = make_workspace("edit-outside")
    allowed_root = make_external_root(workspace, "allowed-edit")
    outside = (allowed_root / "note.txt").resolve()
    outside.write_text("hello old world", encoding="utf-8")

    tool = EditFileTool(workspace, allowed_roots=[allowed_root])

    result = await tool.execute(str(outside), "old", "new")

    assert "Edited" in result
    assert outside.read_text(encoding="utf-8") == "hello new world"


async def test_copy_file_copies_inside_workspace_without_external_prompt() -> None:
    workspace = make_workspace("copy-inside")
    source = workspace / "note.txt"
    destination = workspace / "copies" / "note.txt"
    source.write_text("hello", encoding="utf-8")
    approvals: list[str] = []

    async def approve(prompt: str) -> bool:
        approvals.append(prompt)
        return True

    tool = CopyFileTool(workspace, approval_callback=approve)

    result = await tool.execute("note.txt", "copies/note.txt")

    assert "Copied" in result
    assert destination.read_text(encoding="utf-8") == "hello"
    assert approvals == []


async def test_copy_file_can_copy_to_allowed_external_root() -> None:
    workspace = make_workspace("copy-outside")
    allowed_root = make_external_root(workspace, "allowed-copy")
    outside = allowed_root / "note.txt"
    source = workspace / "note.txt"
    source.write_text("hello", encoding="utf-8")

    tool = CopyFileTool(workspace, allowed_roots=[allowed_root])

    result = await tool.execute("note.txt", str(outside.resolve()))

    assert "Copied" in result
    assert outside.read_text(encoding="utf-8") == "hello"


async def test_copy_file_denies_disallowed_external_destination() -> None:
    workspace = make_workspace("copy-denied")
    outside = workspace.parent / "outside-denied" / "note.txt"
    if outside.parent.exists():
        shutil.rmtree(outside.parent)
    source = workspace / "note.txt"
    source.write_text("hello", encoding="utf-8")

    tool = CopyFileTool(workspace, allowed_roots=[])

    result = await tool.execute("note.txt", str(outside.resolve()))

    assert "requires user approval" in result
    assert "no approval callback" in result
    assert not outside.exists()


async def test_copy_file_refuses_existing_destination_without_overwrite() -> None:
    workspace = make_workspace("copy-existing")
    source = workspace / "note.txt"
    destination = workspace / "copy.txt"
    source.write_text("hello", encoding="utf-8")
    destination.write_text("old", encoding="utf-8")
    tool = CopyFileTool(workspace)

    result = await tool.execute("note.txt", "copy.txt")

    assert "Destination already exists" in result
    assert destination.read_text(encoding="utf-8") == "old"


async def test_move_file_moves_to_allowed_external_root() -> None:
    workspace = make_workspace("move-outside")
    allowed_root = make_external_root(workspace, "allowed-move")
    source = workspace / "note.txt"
    destination = allowed_root / "note.txt"
    source.write_text("hello", encoding="utf-8")
    tool = MoveFileTool(workspace, allowed_roots=[allowed_root])

    result = await tool.execute("note.txt", str(destination.resolve()))

    assert "Moved" in result
    assert not source.exists()
    assert destination.read_text(encoding="utf-8") == "hello"


async def test_move_file_resolves_named_personal_folder_prefix(monkeypatch) -> None:
    workspace = make_workspace("move-named-folder")
    fake_home = workspace.parent / "fake-home"
    if fake_home.exists():
        shutil.rmtree(fake_home)
    desktop = fake_home / "Desktop"
    desktop.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_home.resolve()))
    monkeypatch.setenv("USERPROFILE", str(fake_home.resolve()))
    source = workspace / "note.txt"
    source.write_text("hello", encoding="utf-8")
    tool = MoveFileTool(workspace, allowed_roots=[desktop])

    destination = desktop / "myagent-test-note.txt"

    result = await tool.execute("note.txt", "Desktop/myagent-test-note.txt")

    assert "Moved" in result
    assert not source.exists()
    assert destination.read_text(encoding="utf-8") == "hello"


async def test_move_file_refuses_disallowed_external_destination() -> None:
    workspace = make_workspace("move-denied")
    outside = workspace.parent / "outside-move" / "note.txt"
    if outside.parent.exists():
        shutil.rmtree(outside.parent)
    source = workspace / "note.txt"
    source.write_text("hello", encoding="utf-8")
    tool = MoveFileTool(workspace, allowed_roots=[])

    result = await tool.execute("note.txt", str(outside.resolve()))

    assert "requires user approval" in result
    assert "no approval callback" in result
    assert source.exists()
    assert not outside.exists()


async def test_list_dir_missing_path_suggests_workspace_root() -> None:
    workspace = make_workspace("missing")
    tool = ListDirTool(workspace)

    result = await tool.execute("does-not-exist")

    assert "Directory not found" in result
    assert "path='.'" in result


async def test_default_registry_includes_read_only_file_tools() -> None:
    workspace = make_workspace("registry")
    registry = create_default_registry(workspace)

    assert registry.has("list_dir")
    assert registry.has("read_file")
    assert registry.has("write_file")
    assert registry.has("edit_file")
    assert registry.has("copy_file")
    assert registry.has("move_file")
