"""Visible memory compression for prompt-time memory limits."""

from __future__ import annotations

from dataclasses import dataclass

from myagent.memory.consolidator import SAVE_MEMORY_TOOL, memory_markdown_from_tool_calls
from myagent.memory.markdown import MarkdownMemoryStore
from myagent.providers.base import BaseProvider
from myagent.text.compression import estimate_tokens


@dataclass(frozen=True, slots=True)
class MemoryCompressionResult:
    """Observable result for visible-memory compression."""

    changed: bool
    estimated_tokens: int
    rounds: int
    truncated: bool


class VisibleMemoryCompressor:
    """Compress visible MEMORY.md sections when they exceed a token limit."""

    def __init__(
        self,
        provider: BaseProvider,
        store: MarkdownMemoryStore,
        *,
        token_limit: int = 6000,
        max_rounds: int = 2,
        chars_per_token: int = 4,
    ) -> None:
        self.provider = provider
        self.store = store
        self.token_limit = token_limit
        self.max_rounds = max_rounds
        self.chars_per_token = chars_per_token

    async def compress_if_needed(self) -> MemoryCompressionResult:
        self.store.ensure_layout()
        text = self.store.memory_path.read_text(encoding="utf-8").strip()
        tokens = estimate_tokens(text, self.chars_per_token)
        if tokens <= self.token_limit:
            return MemoryCompressionResult(False, tokens, 0, False)

        new_text = ""
        rounds = 0
        estimated_tokens = tokens
        current = text
        for _ in range(max(self.max_rounds, 0)):
            rounds += 1
            compressed = (await self._compress_once(current)).strip()
            if not compressed:
                break
            new_text = compressed
            estimated_tokens = estimate_tokens(new_text, self.chars_per_token)
            if estimated_tokens <= self.token_limit:
                break
            current = new_text

        if not new_text:
            return MemoryCompressionResult(False, tokens, rounds, False)
        self.store.memory_path.write_text(new_text.rstrip() + "\n", encoding="utf-8")
        return MemoryCompressionResult(
            changed=True,
            estimated_tokens=estimated_tokens,
            rounds=rounds,
            truncated=False,
        )

    async def _compress_once(self, text: str) -> str:
        prompt = (
            "Rewrite this MEMORY.md content to fit the target token limit.\n"
            f"Target token limit: {self.token_limit}\n\n"
            "Keep the same markdown structure with # Memory, ## Always, and ## Now. "
            "Preserve stable user preferences, standing collaboration rules, current "
            "project state, and open loops. Merge duplicates and remove stale or "
            "low-value details. Call save_memory with the complete rewritten "
            "Always and Now sections.\n\n"
            f"{text}"
        )
        response = await self.provider.generate_response(
            [
                {
                    "role": "system",
                    "content": "You compress visible agent memory. Use the save_memory tool.",
                },
                {"role": "user", "content": prompt},
            ],
            tools=SAVE_MEMORY_TOOL,
        )
        return memory_markdown_from_tool_calls(response.tool_calls)
