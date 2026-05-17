"""Automatic memory consolidation: merge memory proposals into MEMORY."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from myagent.memory.markdown import PROPOSALS_HEADER, MarkdownMemoryStore
from myagent.providers.base import BaseProvider


_CONSOLIDATION_SYSTEM_PROMPT = """You are MyAgent's memory consolidation engine.

Your task is to review pending memory proposals and merge them into the current long-term memory.

RULES:
1. Read the current long-term memory and the pending proposals carefully.
2. Merge proposals into the appropriate sections. Each proposal has a target_section indicating where it belongs.
3. DEDUPLICATE: do not keep redundant or near-duplicate information.
4. RESOLVE CONFLICTS: when proposals contradict each other, keep the most accurate/recent one. Discard outdated or wrong information.
5. DISCARD low-quality proposals (importance < 2, vague, or irrelevant).
6. Keep each section concise. Bullet points are preferred.
7. Output ONLY the complete new MEMORY.md content. No extra commentary.

MEMORY STRUCTURE (use exactly these section headings):
# 长期记忆

## Profile
User identity, name, role, background.

## Active Goals
Current long-term goals the user is pursuing.

## Preferences
Stable preferences: tech stack, communication style, path aliases, etc.

## Facts
Important facts to remember: file locations, project info, decisions.

## Notes
Reference notes, observations, lower-confidence information.

If a section has no content after consolidation, keep the heading with a blank line after it.
Do not add any commentary outside the markdown.
"""


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
        if not new_memory or "# 长期记忆" not in new_memory:
            return False

        # Write back
        self.store.memory_path.write_text(new_memory + "\n", encoding="utf-8")

        # Archive proposals instead of deleting
        archive_dir = self.store.root / "memory" / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        archive_path = archive_dir / f"MEMORY_PROPOSALS-{timestamp}.md"
        archive_path.write_text(proposals_text + "\n", encoding="utf-8")

        # Clear proposals
        self.store.proposals_path.write_text(f"{PROPOSALS_HEADER}\n\n", encoding="utf-8")

        return True

    def _build_prompt(self, memory_text: str, proposals_text: str) -> str:
        parts = [
            "## Current Long-term Memory",
            memory_text if memory_text else "(empty)",
            "",
            "## Pending Proposals",
            proposals_text,
            "",
            "Please output the complete new MEMORY.md content.",
        ]
        return "\n".join(parts)
