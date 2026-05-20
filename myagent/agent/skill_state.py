"""Turn-scoped active skill state for AgentLoop."""

from __future__ import annotations

from myagent.agent.run_events import AgentRunEvents


class AgentSkillState:
    """Track active skills loaded during a main-agent turn."""

    def __init__(self, events: AgentRunEvents) -> None:
        self.events = events
        self.active_by_turn: dict[tuple[str, str], list[dict[str, object]]] = {}
        self.current_turn_key: tuple[str, str] | None = None

    def start_turn(self, session_key: str, turn_id: str) -> None:
        self.current_turn_key = (session_key, turn_id)

    def end_turn(self, session_key: str, turn_id: str) -> None:
        self.active_by_turn.pop((session_key, turn_id), None)
        if self.current_turn_key == (session_key, turn_id):
            self.current_turn_key = None

    def trace_event(self, event: str, data: dict[str, object]) -> None:
        """Record skill events and remember active turn skills."""
        turn_id = self.current_turn_key[1] if self.current_turn_key else "skills"
        self.events.record("runtime:skills", turn_id, event, data)
        if event != "active_skill_set" or self.current_turn_key is None:
            return
        active_skills = self.active_by_turn.setdefault(self.current_turn_key, [])
        skill_id = str(data.get("skill_id") or "")
        duplicate = any(str(skill.get("skill_id") or "") == skill_id for skill in active_skills)
        if skill_id and duplicate:
            return
        active_skills.append(dict(data))

    def active_skill_ids_for_turn(self, session_key: str, turn_id: str) -> list[str]:
        """Return active skill ids recorded during this turn."""
        return [
            str(skill.get("skill_id") or "")
            for skill in self.active_by_turn.get((session_key, turn_id), [])
            if skill.get("skill_id")
        ]

    def current_active_skills_context(self) -> str:
        """Return compact active skill context for the current main-agent turn."""
        if self.current_turn_key is None:
            return ""
        session_key, turn_id = self.current_turn_key
        active_skills = self.active_by_turn.get((session_key, turn_id), [])
        if not active_skills:
            return ""
        lines = []
        for skill in active_skills:
            skill_id = str(skill.get("skill_id") or "")
            if not skill_id:
                continue
            name = str(skill.get("name") or skill_id)
            reason = str(skill.get("reason") or "")
            lines.append(f"- {skill_id}: {name}")
            if reason:
                lines.append(f"  reason: {reason}")
        return "\n".join(lines)

    def format_active_skill_context(self, session_key: str, turn_id: str) -> str:
        """Format compact parent active skill context for delegated subagents."""
        active_skills = self.active_by_turn.get((session_key, turn_id), [])
        if not active_skills:
            return ""
        lines = ["# Parent Active Skills"]
        for skill in active_skills:
            skill_id = str(skill.get("skill_id") or "")
            name = str(skill.get("name") or skill_id)
            scope = str(skill.get("scope") or "turn")
            reason = str(skill.get("reason") or "")
            lines.append(f"- {skill_id} ({name}): scope={scope}; reason={reason}")
        return "\n".join(lines)
