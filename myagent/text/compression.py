"""Small LLM compression loop shared by context and memory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable


Compressor = Callable[[str, int], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class CompressionResult:
    """Result of trying to fit text under a token limit."""

    text: str
    estimated_tokens: int
    rounds: int
    truncated: bool


async def compress_until_within_limit(
    text: str,
    *,
    token_limit: int,
    chars_per_token: int,
    max_rounds: int,
    compress_once: Compressor,
) -> CompressionResult:
    """Compress text with an LLM for a few rounds, then truncate if needed."""
    clean = text.strip()
    if token_limit <= 0 or not clean:
        return CompressionResult("", 0, 0, bool(clean))

    tokens = estimate_tokens(clean, chars_per_token)
    if tokens <= token_limit:
        return CompressionResult(clean, tokens, 0, False)

    rounds = 0
    for _ in range(max(max_rounds, 0)):
        rounds += 1
        compressed = (await compress_once(clean, token_limit)).strip()
        if not compressed:
            break
        clean = compressed
        tokens = estimate_tokens(clean, chars_per_token)
        if tokens <= token_limit:
            return CompressionResult(clean, tokens, rounds, False)

    truncated = truncate_to_token_limit(clean, token_limit, chars_per_token)
    return CompressionResult(
        truncated,
        estimate_tokens(truncated, chars_per_token),
        rounds,
        True,
    )


def estimate_tokens(text: str, chars_per_token: int) -> int:
    divisor = max(chars_per_token, 1)
    return max((len(text) + divisor - 1) // divisor, 0)


def truncate_to_token_limit(text: str, token_limit: int, chars_per_token: int) -> str:
    max_chars = max(token_limit, 0) * max(chars_per_token, 1)
    if len(text) <= max_chars:
        return text
    marker = "\n\n[Truncated after compression attempts]"
    if max_chars <= len(marker):
        return text[: max(max_chars, 0)].rstrip()
    return text[: max_chars - len(marker)].rstrip() + marker
