from pathlib import Path
import shutil

from myagent.tools import create_default_registry
from myagent.tools.filesystem import ListDirTool, ReadFileTool, WriteFileTool


def make_workspace(name: str) -> Path:
    root = Path(".test-workspaces") / "filesystem-tools" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
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


async def test_filesystem_tool_blocks_path_escape() -> None:
    workspace = make_workspace("escape")
    outside = (workspace.parent / "outside.txt").resolve()
    outside.write_text("secret", encoding="utf-8")
    tool = ReadFileTool(workspace)

    result = await tool.execute(str(outside))

    assert "outside workspace" in result
    assert str(workspace.resolve()) in result
    assert "Use a relative path" in result


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
