"""Visible memory compression for prompt-time memory limits."""

from __future__ import annotations

from dataclasses import dataclass

from myagent.agent.context.compression import compress_until_within_limit, estimate_tokens
from myagent.memory.markdown import MEMORY_HEADER, MarkdownMemoryStore
from myagent.providers.base import BaseProvider


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
        chars_per_token: int = 4,
    ) -> None:
        self.provider = provider
        self.store = store
        self.chars_per_token = chars_per_token

    async def compress_if_needed(
        self,
        *,
        token_limit: int,
        max_rounds: int,
    ) -> MemoryCompressionResult:
        self.store.ensure_layout()
        text = self.store.memory_path.read_text(encoding="utf-8").strip()
        tokens = estimate_tokens(text, self.chars_per_token)
        if tokens <= token_limit:
            return MemoryCompressionResult(False, tokens, 0, False)

        result = await compress_until_within_limit(
            text,
            token_limit=token_limit,
            chars_per_token=self.chars_per_token,
            max_rounds=max_rounds,
            compress_once=self._compress_once,
        )
        new_text = result.text.strip()
        if MEMORY_HEADER not in new_text:
            new_text = _fallback_memory_text(new_text)
        self.store.memory_path.write_text(new_text.rstrip() + "\n", encoding="utf-8")
        return MemoryCompressionResult(
            changed=True,
            estimated_tokens=result.estimated_tokens,
            rounds=result.rounds,
            truncated=result.truncated,
        )

    async def _compress_once(self, text: str, token_limit: int) -> str:
        prompt = (
            "Rewrite this MEMORY.md content to fit the target token limit.\n"
            f"Target token limit: {token_limit}\n\n"
            "Keep the same markdown structure with # Memory, ## Always, and ## Now. "
            "Preserve stable user preferences, standing collaboration rules, current "
            "project state, and open loops. Merge duplicates and remove stale or "
            "low-value details. Output only the complete rewritten MEMORY.md.\n\n"
            f"{text}"
        )
        return await self.provider.generate(
            [
                {"role": "system", "content": "You compress visible agent memory."},
                {"role": "user", "content": prompt},
            ]
        )


def _fallback_memory_text(content: str) -> str:
    return f"# Memory\n\n## Always\n\n## Now\n\n{content.strip()}"
