"""Automatic memory consolidation: merge memory proposals into MEMORY."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

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
- Extractors and tools may suggest Always or Now, but those suggestions are hints.
- You are responsible for placing each item in the section that best matches its durability and prompt value.

RULES:
1. Read the current memory and the pending proposals carefully.
2. Merge proposals into Always or Now. Treat section_hint as a hint, not a command.
3. DEDUPLICATE: do not keep redundant or near-duplicate information.
4. RESOLVE CONFLICTS: when proposals contradict each other, keep the most accurate/recent one. Discard outdated or wrong information.
5. DISCARD low-quality proposals (importance < 2, vague, or irrelevant).
6. Keep Always and Now within their prompt budgets. Bullet points are preferred.
7. Call the save_memory tool with the complete new MEMORY.md content. No free-text reply.

WHEN A VISIBLE SECTION IS TOO LARGE:
1. Merge duplicates and near-duplicates.
2. Compress related details into one higher-level bullet.
3. Demote stale or lower-value Always items to Now.
4. Remove completed or no-longer-active Now items from visible memory; archive is handled separately.
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

If a section has no content after consolidation, keep the heading with a blank line after it.
Do not add any commentary outside the markdown.
""".format(
    always_budget=ALWAYS_MEMORY_CHAR_BUDGET,
    now_budget=NOW_MEMORY_CHAR_BUDGET,
)

SAVE_MEMORY_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save the validated long-term memory consolidation result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_markdown": {
                        "type": "string",
                        "description": "The complete updated MEMORY.md markdown with # Memory, ## Always, and ## Now.",
                    },
                },
                "required": ["memory_markdown"],
            },
        },
    }
]


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
            response = await self.provider.generate_response(
                [
                    {"role": "system", "content": _CONSOLIDATION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                tools=SAVE_MEMORY_TOOL,
            )
        except Exception:
            return False

        new_memory = memory_markdown_from_tool_calls(response.tool_calls)
        if not new_memory:
            return False

        self.store.memory_path.write_text(new_memory.rstrip() + "\n", encoding="utf-8")

        archive_dir = self.store.root / "archive" / "proposals"
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
            "Please call save_memory with the complete new MEMORY.md content.",
        ]
        return "\n".join(parts)


def memory_markdown_from_tool_calls(tool_calls: list[Any]) -> str:
    """Extract and normalize MEMORY.md content from a save_memory tool call."""
    if not tool_calls:
        return ""
    call = tool_calls[0]
    if getattr(call, "name", "") != "save_memory":
        return ""
    arguments = _normalize_arguments(getattr(call, "arguments", {}))
    if arguments is None:
        return ""
    markdown = arguments.get("memory_markdown")
    if markdown is None:
        return ""
    return _normalize_memory_markdown(_ensure_text(markdown))


def _normalize_arguments(arguments: object) -> dict[str, object] | None:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return None
    if isinstance(arguments, list):
        return arguments[0] if arguments and isinstance(arguments[0], dict) else None
    return arguments if isinstance(arguments, dict) else None


def _ensure_text(value: object) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _normalize_memory_markdown(markdown: str) -> str:
    """Keep MEMORY.md in the small canonical shape this project expects."""
    sections = _parse_visible_sections(markdown)
    if not sections:
        return ""
    always = sections.get("Always")
    now = sections.get("Now")
    if always is None or now is None:
        return ""
    return (
        f"{MEMORY_HEADER}\n\n"
        f"## Always\n\n{always.strip()}\n\n"
        f"## Now\n\n{now.strip()}"
    ).rstrip()


def _parse_visible_sections(markdown: str) -> dict[str, str] | None:
    lines = markdown.strip().splitlines()
    if not lines or lines[0].strip() != MEMORY_HEADER:
        return None
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines[1:]:
        clean = line.strip()
        if clean.startswith("## "):
            current = clean.removeprefix("## ").strip()
            sections.setdefault(current, [])
            continue
        if current in {"Always", "Now"}:
            sections[current].append(line)
    return {name: "\n".join(section_lines).strip() for name, section_lines in sections.items()}
