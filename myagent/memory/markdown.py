"""Markdown-backed memory store for the personal-agent memory layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import re
from uuid import uuid4


VISIBLE_MEMORY_SECTIONS = ("Always", "Now")
SEARCHABLE_MEMORY_SECTIONS = ("Later",)
MEMORY_HEADER = "# Memory"
PROPOSALS_HEADER = "# Memory Proposals"
ALWAYS_MEMORY_CHAR_BUDGET = 4000
NOW_MEMORY_CHAR_BUDGET = 8000


@dataclass(frozen=True, slots=True)
class MarkdownMemoryRecord:
    """One searchable markdown memory chunk."""

    id: str
    source: str
    section: str
    content: str
    score: int = 0


class MarkdownMemoryStore:
    """Store human-reviewable personal memory in local Markdown files."""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else Path.home() / ".myagent" / "memory"
        self.memory_path = self.root / "MEMORY.md"
        self.proposals_path = self.root / "MEMORY_PROPOSALS.md"
        self.dreams_path = self.proposals_path
        self.daily_dir = self.root / "daily"

    def ensure_layout(self) -> None:
        """Create the default local memory files if they do not exist."""
        self.daily_dir.mkdir(parents=True, exist_ok=True)
        if not self.memory_path.exists():
            self.memory_path.write_text(_default_memory_text(), encoding="utf-8")
        if not self.proposals_path.exists():
            self.proposals_path.write_text(f"{PROPOSALS_HEADER}\n\n", encoding="utf-8")

    def read_always_memory(self) -> str:
        """Return compact stable memory that should normally survive budgeting."""
        return self.read_visible_memory_sections().get("Always", "").strip()

    def read_now_memory(self) -> str:
        """Return compact current working memory for the active project phase."""
        return self.read_visible_memory_sections().get("Now", "").strip()

    def read_visible_memory_sections(self) -> dict[str, str]:
        """Return visible MEMORY.md sections keyed by section name."""
        if not self.memory_path.exists():
            return {}
        sections = _parse_markdown_sections(self.memory_path.read_text(encoding="utf-8"))
        return {name: sections.get(name, "").strip() for name in VISIBLE_MEMORY_SECTIONS}

    def append_daily(
        self,
        note: str,
        tags: list[str] | None = None,
        importance: int = 1,
        source: str = "agent",
        day: date | None = None,
    ) -> MarkdownMemoryRecord:
        """Append one working note or candidate to today's daily memory file."""
        self.ensure_layout()
        target_day = day or date.today()
        path = self.daily_dir / f"{target_day.isoformat()}.md"
        if not path.exists():
            path.write_text(f"# Daily Memory {target_day.isoformat()}\n\n", encoding="utf-8")

        memory_id = f"daily-{target_day.strftime('%Y%m%d')}-{uuid4().hex[:8]}"
        clean_note = note.strip()
        tag_text = ", ".join(tags or [])
        timestamp = datetime.now().isoformat(timespec="seconds")
        block = (
            f"\n## {memory_id}\n\n"
            f"- source: {source}\n"
            f"- importance: {importance}\n"
            f"- tags: {tag_text}\n"
            f"- created_at: {timestamp}\n\n"
            f"{clean_note}\n"
        )
        with path.open("a", encoding="utf-8") as file:
            file.write(block)
        return MarkdownMemoryRecord(
            id=memory_id,
            source=str(path.relative_to(self.root)),
            section=memory_id,
            content=clean_note,
        )

    def propose_long_term(
        self,
        content: str,
        section: str,
        tags: list[str] | None = None,
        importance: int = 3,
        source: str = "agent",
        apply: bool = False,
    ) -> MarkdownMemoryRecord:
        """Record a proposal for promotion to long-term memory."""
        self.ensure_layout()
        if apply:
            return self.append_long_term(content=content, section=section, tags=tags)

        proposal_id = f"proposal-{uuid4().hex[:8]}"
        tag_text = ", ".join(tags or [])
        timestamp = datetime.now().isoformat(timespec="seconds")
        clean_content = content.strip()
        block = (
            f"\n## {proposal_id}\n\n"
            f"- target_section: {section}\n"
            f"- source: {source}\n"
            f"- importance: {importance}\n"
            f"- tags: {tag_text}\n"
            f"- created_at: {timestamp}\n\n"
            f"{clean_content}\n"
        )
        with self.proposals_path.open("a", encoding="utf-8") as file:
            file.write(block)
        return MarkdownMemoryRecord(
            id=proposal_id,
            source=self.proposals_path.name,
            section=proposal_id,
            content=clean_content,
        )

    def append_long_term(
        self,
        content: str,
        section: str,
        tags: list[str] | None = None,
    ) -> MarkdownMemoryRecord:
        """Append one reviewed long-term memory bullet to MEMORY.md."""
        self.ensure_layout()
        clean_content = content.strip()
        target_section = section.strip() or "Later"
        memory_id = f"memory-{uuid4().hex[:8]}"
        marker = f"<!-- id: {memory_id} tags: {', '.join(tags or [])} -->"
        text = self.memory_path.read_text(encoding="utf-8")
        updated = _append_to_markdown_section(
            text,
            target_section,
            f"- {clean_content} {marker}",
        )
        self.memory_path.write_text(updated, encoding="utf-8")
        return MarkdownMemoryRecord(
            id=memory_id,
            source=self.memory_path.name,
            section=target_section,
            content=clean_content,
        )

    def forget(self, query: str) -> list[MarkdownMemoryRecord]:
        """Remove matching memory chunks or bullets from markdown memory files."""
        self.ensure_layout()
        clean_query = query.strip()
        if not clean_query:
            return []

        forgotten: list[MarkdownMemoryRecord] = []
        for path in self._memory_files():
            text = path.read_text(encoding="utf-8")
            updated, removed = _forget_from_markdown(text, clean_query, self.root, path)
            if removed:
                path.write_text(updated, encoding="utf-8")
                forgotten.extend(removed)
        return forgotten

    def search(self, query: str, limit: int = 5) -> list[MarkdownMemoryRecord]:
        """Search markdown memory with a simple explainable keyword score."""
        terms = _terms(query)
        records = self._records()
        scored: list[MarkdownMemoryRecord] = []
        for record in records:
            content_terms = _terms(record.content)
            score = len(terms & content_terms) if terms else 0
            if score > 0 or not terms:
                scored.append(
                    MarkdownMemoryRecord(
                        id=record.id,
                        source=record.source,
                        section=record.section,
                        content=record.content,
                        score=score,
                    )
                )
        scored.sort(key=lambda record: (record.score, record.id), reverse=True)
        return scored[:limit]

    def get(self, memory_id: str) -> MarkdownMemoryRecord | None:
        """Return a markdown memory chunk by id."""
        for record in self._records():
            if record.id == memory_id:
                return record
        return None

    def _records(self) -> list[MarkdownMemoryRecord]:
        records: list[MarkdownMemoryRecord] = []
        for path in self._memory_files():
            records.extend(_records_from_file(self.root, path))
        return records

    def _memory_files(self) -> list[Path]:
        paths: list[Path] = []
        if self.memory_path.exists():
            paths.append(self.memory_path)
        if self.proposals_path.exists():
            paths.append(self.proposals_path)
        if self.daily_dir.exists():
            paths.extend(sorted(self.daily_dir.glob("*.md")))
        return paths


def _records_from_file(root: Path, path: Path) -> list[MarkdownMemoryRecord]:
    text = path.read_text(encoding="utf-8")
    relative = str(path.relative_to(root))
    sections = _parse_markdown_sections(text)
    records: list[MarkdownMemoryRecord] = []
    for section, content in sections.items():
        clean_content = content.strip()
        if not clean_content:
            continue
        if _looks_like_memory_id(section):
            clean_content = _strip_metadata_block(clean_content)
        if section in VISIBLE_MEMORY_SECTIONS and path.name == "MEMORY.md":
            continue
        record_id = section if _looks_like_memory_id(section) else f"{relative}#{section}"
        records.append(
            MarkdownMemoryRecord(
                id=record_id,
                source=relative,
                section=section,
                content=clean_content,
            )
        )
    return records


def _default_memory_text() -> str:
    return (
        f"{MEMORY_HEADER}\n\n"
        "## Always\n\n"
        "## Now\n\n"
        "## Later\n"
    )


def _append_to_markdown_section(text: str, section: str, line: str) -> str:
    lines = text.splitlines()
    heading = f"## {section}"
    for index, current_line in enumerate(lines):
        if current_line.strip() != heading:
            continue
        insert_at = len(lines)
        for next_index in range(index + 1, len(lines)):
            if lines[next_index].startswith("## "):
                insert_at = next_index
                break
        before = lines[:insert_at]
        after = lines[insert_at:]
        if before and before[-1].strip():
            before.append("")
        before.append(line)
        if after and (not before or before[-1].strip()):
            before.append("")
        return "\n".join(before + after).rstrip() + "\n"

    if lines and lines[-1].strip():
        lines.append("")
    lines.extend([heading, "", line])
    return "\n".join(lines).rstrip() + "\n"


def _forget_from_markdown(
    text: str,
    query: str,
    root: Path,
    path: Path,
) -> tuple[str, list[MarkdownMemoryRecord]]:
    removed: list[MarkdownMemoryRecord] = []
    sections = _split_markdown_sections(text)
    output: list[str] = []
    relative = str(path.relative_to(root))
    terms = _terms(query)

    for heading, body_lines in sections:
        if heading is None:
            output.extend(body_lines)
            continue

        section = heading.removeprefix("## ").strip()
        body = "\n".join(body_lines).strip()
        section_id = _extract_section_memory_id(section, body)
        if section_id and (query == section_id or _matches_query(body, terms, query)):
            removed.append(
                MarkdownMemoryRecord(
                    id=section_id,
                    source=relative,
                    section=section,
                    content=_strip_metadata_block(body),
                )
            )
            continue

        output.append(heading)
        for line in body_lines:
            line_id = _extract_inline_memory_id(line)
            if line_id and (query == line_id or _matches_query(line, terms, query)):
                removed.append(
                    MarkdownMemoryRecord(
                        id=line_id,
                        source=relative,
                        section=section,
                        content=_clean_memory_line(line),
                    )
                )
                continue
            if not line_id and line.lstrip().startswith("- ") and _matches_query(line, terms, query):
                removed.append(
                    MarkdownMemoryRecord(
                        id=f"{relative}#{section}",
                        source=relative,
                        section=section,
                        content=_clean_memory_line(line),
                    )
                )
                continue
            output.append(line)

    return "\n".join(output).rstrip() + "\n", removed


def _split_markdown_sections(text: str) -> list[tuple[str | None, list[str]]]:
    sections: list[tuple[str | None, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            sections.append((current_heading, current_lines))
            current_heading = line
            current_lines = []
            continue
        current_lines.append(line)
    sections.append((current_heading, current_lines))
    return sections


def _matches_query(text: str, terms: set[str], raw_query: str) -> bool:
    if raw_query and raw_query in text:
        return True
    text_terms = _terms(text)
    return bool(terms and terms <= text_terms)


def _extract_section_memory_id(section: str, body: str) -> str | None:
    if _looks_like_memory_id(section):
        return section
    match = re.search(r"<!--\s*id:\s*([A-Za-z0-9_-]+)", body)
    if match:
        return match.group(1)
    return None


def _extract_inline_memory_id(line: str) -> str | None:
    match = re.search(r"<!--\s*id:\s*([A-Za-z0-9_-]+)", line)
    if match:
        return match.group(1)
    return None


def _clean_memory_line(line: str) -> str:
    without_marker = re.sub(r"\s*<!--.*?-->", "", line).strip()
    return without_marker.removeprefix("- ").strip()


def _parse_markdown_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            current = match.group(1)
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def _looks_like_memory_id(section: str) -> bool:
    return section.startswith(("daily-", "proposal-"))


def _strip_metadata_block(content: str) -> str:
    lines = content.splitlines()
    index = 0
    while index < len(lines) and lines[index].startswith("- "):
        index += 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    return "\n".join(lines[index:]).strip()


def _terms(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text)
        if token.strip()
    }
