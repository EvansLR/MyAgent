"""Automatic memory consolidation: merge memory proposals into MEMORY."""

from __future__ import annotations

from datetime import datetime

from myagent.memory.markdown import (
    ALWAYS_MEMORY_CHAR_BUDGET,
    MEMORY_HEADER,
    NOW_MEMORY_CHAR_BUDGET,
    PROPOSALS_HEADER,
    MarkdownMemoryStore,
)
from myagent.providers.base import BaseProvider


_CONSOLIDATION_SYSTEM_PROMPT = """You are MyAgent's memory consolidation engine.

Your task is to review pending memory proposals and merge them into the current long-term memory.

SECTION DECISION:
- Extractors and tools may suggest Always, Now, or Later, but those suggestions are hints.
- You are responsible for placing each item in the section that best matches its durability and prompt value.

RULES:
1. Read the current memory and the pending proposals carefully.
2. Merge proposals into Always, Now, or Later. Treat target_section as a hint, not a command.
3. DEDUPLICATE: do not keep redundant or near-duplicate information.
4. RESOLVE CONFLICTS: when proposals contradict each other, keep the most accurate/recent one. Discard outdated or wrong information.
5. DISCARD low-quality proposals (importance < 2, vague, or irrelevant).
6. Keep Always and Now within their prompt budgets. Bullet points are preferred.
7. Output ONLY the complete new MEMORY.md content. No extra commentary.

WHEN A VISIBLE SECTION IS TOO LARGE:
1. Merge duplicates and near-duplicates.
2. Compress related details into one higher-level bullet.
3. Demote stale or lower-value Always items to Now or Later.
4. Demote completed or no-longer-active Now items to Later.
5. Discard only low-quality, contradicted, or obsolete information.
Do not delete an item merely because it is old.

MEMORY STRUCTURE (use exactly these section headings):
# Memory

## Always
Stable, high-signal information that should be visible in every conversation.
Keep this very short. Prefer durable user preferences, identity/background, and
standing collaboration rules. Target budget: {always_budget} characters.

## Now
Current stage, active project state, open loops, and recent decisions that should
stay visible for the next few sessions. Target budget: {now_budget} characters.

## Later
Useful but non-urgent facts, historical context, references, and lower-confidence
notes. This section is searchable but not injected into the prompt by default.

If a section has no content after consolidation, keep the heading with a blank line after it.
Do not add any commentary outside the markdown.
""".format(
    always_budget=ALWAYS_MEMORY_CHAR_BUDGET,
    now_budget=NOW_MEMORY_CHAR_BUDGET,
)


class MemoryConsolidator:
    """Periodically merge MEMORY_PROPOSALS.md proposals into MEMORY.md using an LLM."""

    def __init__(self, provider: BaseProvider, store: MarkdownMemoryStore) -> None:
        self.provider = provider
        self.store = store

    async def consolidate(self) -> bool:
        """Merge memory proposals into MEMORY. Return True if work was done."""
        if not self.store.proposals_path.exists():
            return False

        proposals_text = self.store.proposals_path.read_text(encoding="utf-8").strip()
        if not proposals_text or proposals_text == PROPOSALS_HEADER:
            return False

        memory_text = ""
        if self.store.memory_path.exists():
            memory_text = self.store.memory_path.read_text(encoding="utf-8").strip()

        prompt = self._build_prompt(memory_text, proposals_text)

        try:
            response = await self.provider.generate([
                {"role": "system", "content": _CONSOLIDATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ])
        except Exception:
            return False

        new_memory = response.strip()
        if not new_memory or MEMORY_HEADER not in new_memory:
            return False

        self.store.memory_path.write_text(new_memory + "\n", encoding="utf-8")

        archive_dir = self.store.root / "memory" / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        archive_path = archive_dir / f"MEMORY_PROPOSALS-{timestamp}.md"
        archive_path.write_text(proposals_text + "\n", encoding="utf-8")

        self.store.proposals_path.write_text(f"{PROPOSALS_HEADER}\n\n", encoding="utf-8")

        return True

    def _build_prompt(self, memory_text: str, proposals_text: str) -> str:
        parts = [
            "## Current Memory",
            memory_text if memory_text else "(empty)",
            "",
            "## Pending Proposals",
            proposals_text,
            "",
            "Please output the complete new MEMORY.md content.",
        ]
        return "\n".join(parts)
