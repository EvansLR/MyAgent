from typing import Any

from myagent.tools.base import Tool
from myagent.tools.registry import ToolRegistry


class AddTool(Tool):
    @property
    def name(self) -> str:
        return "add"

    @property
    def description(self) -> str:
        return "Add two integers."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
            "required": ["a", "b"],
        }

    async def execute(self, a: int, b: int) -> str:
        return str(a + b)


def test_registry_registers_and_finds_tool() -> None:
    registry = ToolRegistry()
    tool = AddTool()

    registry.register(tool)

    assert registry.get("add") is tool
    assert registry.has("add")
    assert "add" in registry


async def test_registry_rejects_unknown_tool() -> None:
    registry = ToolRegistry()

    result = await registry.execute("missing", {})

    assert result.startswith("Error: Tool 'missing' not found")


async def test_registry_validates_required_params() -> None:
    registry = ToolRegistry()
    registry.register(AddTool())

    result = await registry.execute("add", {"a": 1})

    assert "missing required b" in result


async def test_registry_casts_basic_param_types() -> None:
    registry = ToolRegistry()
    registry.register(AddTool())

    result = await registry.execute("add", {"a": "2", "b": "3"})

    assert result == "5"


def test_registry_returns_openai_tool_definitions() -> None:
    registry = ToolRegistry()
    registry.register(AddTool())

    definitions = registry.get_definitions()

    assert definitions[0]["type"] == "function"
    assert definitions[0]["function"]["name"] == "add"


def test_default_registry_includes_web_search() -> None:
    from myagent.tools import create_default_registry

    registry = create_default_registry()

    assert registry.has("edit_file")
    assert registry.has("copy_file")
    assert registry.has("move_file")
    assert registry.has("web_search")
    assert registry.has("web_fetch")
