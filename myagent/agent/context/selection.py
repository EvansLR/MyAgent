"""Prompt rendering and history selection helpers."""

from __future__ import annotations

from myagent.agent.context.types import ContextBudget, ContextSection, Message


def estimate_tokens(text: str, chars_per_token: int) -> int:
    divisor = max(chars_per_token, 1)
    return max((len(text) + divisor - 1) // divisor, 0)


def render_system_prompt(sections: list[ContextSection]) -> str:
    """Render non-empty system sections into one system prompt."""
    return "\n\n---\n\n".join(
        f"# {section.name}\n\n{section.content.strip()}"
        for section in sections
        if section.content.strip()
    )


def select_history(
    history: list[Message],
    budget: ContextBudget,
    max_history_tokens: int | None = None,
) -> list[Message]:
    """Select the history slice visible to the current model call."""
    selected = list(history)
    if max_history_tokens is not None:
        selected = _limit_history_by_token_count(selected, max_history_tokens, budget)
    selected = _limit_history_by_message_count(selected, budget)
    return drop_invalid_leading_history(selected)


def drop_invalid_leading_history(history: list[Message]) -> list[Message]:
    """Keep selected chat history in a valid user-starting shape."""
    selected = list(history)
    while selected and selected[0].get("role") != "user":
        selected.pop(0)
    return selected


def _limit_history_by_message_count(
    history: list[Message],
    budget: ContextBudget,
) -> list[Message]:
    if budget.max_history_messages is None:
        return list(history)
    max_messages = max(budget.max_history_messages, 0)
    return list(history[-max_messages:] if max_messages else [])


def _limit_history_by_token_count(
    history: list[Message],
    max_history_tokens: int,
    budget: ContextBudget,
) -> list[Message]:
    selected_reversed: list[Message] = []
    used_tokens = 0
    for message in reversed(history):
        tokens = estimate_tokens(
            str(message.get("content", "")),
            budget.chars_per_token,
        )
        if used_tokens + tokens <= max_history_tokens:
            selected_reversed.append(message)
            used_tokens += tokens
    return list(reversed(selected_reversed))
