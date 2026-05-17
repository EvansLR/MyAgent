"""Memory tools exposed to the main agent."""

from typing import Any

from myagent.memory.markdown import MarkdownMemoryStore
from myagent.tools.base import Tool


class MemoryAppendDailyTool(Tool):
    """Append a daily working-memory note."""

    def __init__(self, store: MarkdownMemoryStore) -> None:
        self.store = store

    @property
    def name(self) -> str:
        return "memory_append_daily"

    @property
    def description(self) -> str:
        return (
            "Append a short working-memory note or candidate observation to today's "
            "local daily memory file."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "note": {"type": "string", "description": "Standalone memory note."},
                "tags": {"type": "array", "description": "Optional tags."},
                "importance": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "Importance from 1 to 5.",
                },
            },
            "required": ["note"],
        }

    async def execute(
        self,
        note: str,
        tags: list[str] | None = None,
        importance: int = 1,
        **_: Any,
    ) -> str:
        record = self.store.append_daily(note=note, tags=tags, importance=importance)
        return f"Saved daily memory {record.id} in {record.source}."


class MemoryProposeLongTermTool(Tool):
    """Create or apply a long-term memory."""

    def __init__(self, store: MarkdownMemoryStore) -> None:
        self.store = store

    @property
    def name(self) -> str:
        return "memory_propose_long_term"

    @property
    def description(self) -> str:
        return (
            "Create a durable long-term memory proposal. Use apply=true only when "
            "the user explicitly asks you to remember stable profile, preference, "
            "goal, or project information."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Standalone memory content."},
                "section": {
                    "type": "string",
                    "description": "Suggested MEMORY.md section, such as Core Memory.",
                },
                "tags": {"type": "array", "description": "Optional tags."},
                "importance": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "Importance from 1 to 5.",
                },
                "apply": {
                    "type": "boolean",
                    "description": "Whether to write directly to MEMORY.md. Default false.",
                },
            },
            "required": ["content", "section"],
        }

    async def execute(
        self,
        content: str,
        section: str,
        tags: list[str] | None = None,
        importance: int = 3,
        apply: bool = False,
        **_: Any,
    ) -> str:
        record = self.store.propose_long_term(
            content=content,
            section=section,
            tags=tags,
            importance=importance,
            apply=apply,
        )
        if apply:
            return f"Saved long-term memory {record.id} in {record.source}#{record.section}."
        return f"Created long-term memory proposal {record.id} in {record.source}."


class MemoryForgetTool(Tool):
    """Forget matching markdown memories."""

    def __init__(self, store: MarkdownMemoryStore) -> None:
        self.store = store

    @property
    def name(self) -> str:
        return "memory_forget"

    @property
    def description(self) -> str:
        return (
            "Forget memories matching a memory id or exact topic. Use this when "
            "the user asks to forget, remove, delete, or stop remembering something."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Memory id or text/topic to forget.",
                }
            },
            "required": ["query"],
        }

    async def execute(self, query: str, **_: Any) -> str:
        forgotten = self.store.forget(query)
        if not forgotten:
            return f"No matching markdown memory found for '{query}'."
        lines = [f"Forgot {len(forgotten)} markdown memory item(s):"]
        lines.extend(
            f"- {record.id} from {record.source}#{record.section}: {record.content}"
            for record in forgotten
        )
        return "\n".join(lines)


class MemorySearchTool(Tool):
    """Search markdown-backed memory."""

    def __init__(self, store: MarkdownMemoryStore) -> None:
        self.store = store

    @property
    def name(self) -> str:
        return "memory_search"

    @property
    def description(self) -> str:
        return (
            "Search out-of-context memory such as daily notes, memory proposals, and "
            "non-core MEMORY.md sections."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."},
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "description": "Maximum result count.",
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, limit: int = 5, **_: Any) -> str:
        records = self.store.search(query=query, limit=limit)
        if not records:
            return "No memory results found."
        return "\n\n".join(
            f"- id: {record.id}\n"
            f"  source: {record.source}\n"
            f"  section: {record.section}\n"
            f"  score: {record.score}\n"
            f"  content: {record.content}"
            for record in records
        )


class MemoryGetTool(Tool):
    """Retrieve one memory chunk."""

    def __init__(self, store: MarkdownMemoryStore) -> None:
        self.store = store

    @property
    def name(self) -> str:
        return "memory_get"

    @property
    def description(self) -> str:
        return "Retrieve a full memory chunk by memory_id."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "memory_id": {"type": "string", "description": "Memory id returned by search."}
            },
            "required": ["memory_id"],
        }

    async def execute(self, memory_id: str, **_: Any) -> str:
        record = self.store.get(memory_id)
        if record is None:
            return f"Memory '{memory_id}' not found."
        return (
            f"id: {record.id}\n"
            f"source: {record.source}\n"
            f"section: {record.section}\n\n"
            f"{record.content}"
        )
