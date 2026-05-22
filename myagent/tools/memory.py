"""Memory tools exposed to the main agent."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from myagent.memory.markdown import MarkdownMemoryStore
from myagent.tools.base import Tool

if TYPE_CHECKING:
    from myagent.memory.consolidator import MemoryConsolidator


class MemoryArchiveTool(Tool):
    """Append an episodic archive note."""

    def __init__(self, store: MarkdownMemoryStore) -> None:
        self.store = store

    @property
    def name(self) -> str:
        return "memory_archive"

    @property
    def description(self) -> str:
        return (
            "Append a short episodic note to searchable archive. Use for completed "
            "work, temporary observations, or historical context that should not "
            "change the default prompt."
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
        record = self.store.append_archive(note=note, tags=tags, importance=importance)
        return f"Archived memory note {record.id} in {record.source}."


class MemoryConsolidateTool(Tool):
    """Merge pending memory proposals into visible memory."""

    def __init__(self, consolidator: MemoryConsolidator) -> None:
        self.consolidator = consolidator

    @property
    def name(self) -> str:
        return "memory_consolidate"

    @property
    def description(self) -> str:
        return (
            "Review pending memory proposals and merge useful ones into MEMORY.md. "
            "Use when the user asks to tidy, consolidate, or process memory proposals, "
            "or when a scheduled maintenance task asks you to organize memory."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, **_: Any) -> str:
        changed = await self.consolidator.consolidate()
        if changed:
            return "Consolidated pending memory proposals into MEMORY.md."
        return "No pending memory proposals to consolidate."


class MemoryRememberTool(Tool):
    """Write explicit visible memory."""

    def __init__(self, store: MarkdownMemoryStore) -> None:
        self.store = store

    @property
    def name(self) -> str:
        return "memory_remember"

    @property
    def description(self) -> str:
        return (
            "Immediately remember explicit user-approved information in visible "
            "memory. Use only when the user asks you to remember something or "
            "clearly establishes durable/current context. Sections: Always or Now."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Standalone memory content."},
                "section": {
                    "type": "string",
                    "description": "Visible memory section: Always or Now.",
                },
                "tags": {"type": "array", "description": "Optional tags."},
            },
            "required": ["content", "section"],
        }

    async def execute(
        self,
        content: str,
        section: str,
        tags: list[str] | None = None,
        **_: Any,
    ) -> str:
        record = self.store.remember(
            content=content,
            section=section,
            tags=tags,
        )
        return f"Remembered {record.id} in {record.source}#{record.section}."


class MemoryProposeTool(Tool):
    """Create a candidate visible memory."""

    def __init__(self, store: MarkdownMemoryStore) -> None:
        self.store = store

    @property
    def name(self) -> str:
        return "memory_propose"

    @property
    def description(self) -> str:
        return (
            "Create a candidate memory proposal for later consolidation. Use when "
            "information may be useful but was not explicitly approved for immediate "
            "visible memory. Section hints: Always or Now."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Standalone candidate memory."},
                "section_hint": {
                    "type": "string",
                    "description": "Suggested visible section: Always or Now.",
                },
                "tags": {"type": "array", "description": "Optional tags."},
                "importance": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "Importance from 1 to 5.",
                },
            },
            "required": ["content", "section_hint"],
        }

    async def execute(
        self,
        content: str,
        section_hint: str,
        tags: list[str] | None = None,
        importance: int = 3,
        **_: Any,
    ) -> str:
        record = self.store.propose_memory(
            content=content,
            section_hint=section_hint,
            tags=tags,
            importance=importance,
        )
        return f"Created memory proposal {record.id} in {record.source}."


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
            "Search out-of-context memory such as archive notes and memory proposals."
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
