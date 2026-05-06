from pathlib import Path
import shutil

from myagent.tools import create_default_registry
from myagent.tools.filesystem import ListDirTool, ReadFileTool


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


async def test_default_registry_includes_read_only_file_tools() -> None:
    workspace = make_workspace("registry")
    registry = create_default_registry(workspace)

    assert registry.has("list_dir")
    assert registry.has("read_file")
