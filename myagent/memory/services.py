"""Memory service assembly for the agent runtime."""

from __future__ import annotations

from dataclasses import dataclass

from myagent.memory.compressor import VisibleMemoryCompressor
from myagent.memory.consolidator import MemoryConsolidator
from myagent.memory.extractor import MemoryExtractor
from myagent.memory.markdown import MarkdownMemoryStore
from myagent.providers.base import BaseProvider
from myagent.tools.registry import ToolRegistry


@dataclass(slots=True)
class AgentMemoryServices:
    """Own the memory collaborators used by the agent runtime."""

    store: MarkdownMemoryStore
    extractor: MemoryExtractor
    consolidator: MemoryConsolidator
    compressor: VisibleMemoryCompressor

    @classmethod
    def create(
        cls,
        provider: BaseProvider,
        *,
        store: MarkdownMemoryStore | None = None,
        extractor: MemoryExtractor | None = None,
        chars_per_token: int = 4,
    ) -> "AgentMemoryServices":
        memory_store = store or MarkdownMemoryStore()
        return cls(
            store=memory_store,
            extractor=extractor or MemoryExtractor(provider, memory_store),
            consolidator=MemoryConsolidator(provider, memory_store),
            compressor=VisibleMemoryCompressor(
                provider,
                memory_store,
                chars_per_token=chars_per_token,
            ),
        )

    def apply_chars_per_token(self, chars_per_token: int) -> None:
        """Align prompt-time memory compression with the active context estimate."""
        self.compressor.chars_per_token = chars_per_token

    def register_tools(self, registry: ToolRegistry) -> None:
        """Expose memory tools without leaking concrete tool classes to AgentLoop."""
        from myagent.tools import (
            MemoryArchiveTool,
            MemoryForgetTool,
            MemoryGetTool,
            MemoryProposeTool,
            MemoryRememberTool,
            MemorySearchTool,
        )

        tools = (
            MemoryRememberTool(self.store),
            MemoryProposeTool(self.store),
            MemoryArchiveTool(self.store),
            MemorySearchTool(self.store),
            MemoryGetTool(self.store),
            MemoryForgetTool(self.store),
        )
        for tool in tools:
            if not registry.has(tool.name):
                registry.register(tool)
