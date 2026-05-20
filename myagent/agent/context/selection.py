"""History, prompt item, and report helpers for context building."""

from __future__ import annotations

from myagent.agent.context.types import (
    ContextAssemblyReport,
    ContextBudget,
    ContextHistoryReport,
    ContextItem,
    ContextSection,
    ContextSectionReport,
    Message,
)
from myagent.bus import InboundMessage


def estimate_tokens(text: str, chars_per_token: int) -> int:
    divisor = max(chars_per_token, 1)
    return max((len(text) + divisor - 1) // divisor, 0)


def items_from_sections(
    sections: list[ContextSection],
    budget: ContextBudget,
) -> list[ContextItem]:
    """Convert public sections into internal budgetable items."""
    items = []
    for order, section in enumerate(sections):
        content = section.content.strip()
        items.append(
            ContextItem(
                id=f"{section.source}:{section.name}",
                name=section.name,
                kind=section.kind,
                retention=section.retention,
                order=order,
                source=section.source,
                content=content,
                estimated_tokens=estimate_tokens(content, budget.chars_per_token),
            )
        )
    return items


def select_system_items(
    items: list[ContextItem],
) -> tuple[list[ContextItem], list[ContextSectionReport], list[str]]:
    """Return non-empty system context items without prompt-time competition."""
    non_empty = [item for item in items if item.content.strip()]
    selected_ids = {item.id for item in non_empty}
    return (
        sorted(non_empty, key=lambda item: item.order),
        section_reports(items, selected_ids, {}),
        [],
    )


def section_reports(
    items: list[ContextItem],
    selected_ids: set[str],
    dropped_reasons: dict[str, str],
) -> list[ContextSectionReport]:
    """Build section reports for both included and dropped items."""
    reports = []
    for item in sorted(items, key=lambda value: value.order):
        has_content = bool(item.content.strip())
        included = item.id in selected_ids
        reason = "included" if included else dropped_reasons.get(item.id, "empty")
        if has_content and not included and reason == "empty":
            reason = "budget_exceeded"
        reports.append(
            ContextSectionReport(
                name=item.name,
                kind=item.kind.value,
                retention=item.retention.value,
                source=item.source,
                chars=len(item.content),
                estimated_tokens=item.estimated_tokens,
                included=included,
                reason=reason,
            )
        )
    return reports


def render_system_prompt(items: list[ContextItem]) -> str:
    """Render selected system items into a model system prompt."""
    return "\n\n---\n\n".join(
        f"# {item.name}\n\n{item.content}" for item in items if item.content.strip()
    )


def select_history(
    history: list[Message],
    budget: ContextBudget,
    max_history_tokens: int | None = None,
    reserved_history_tokens: int = 0,
) -> tuple[list[Message], ContextHistoryReport, list[str]]:
    """Select the history slice visible to the current model call."""
    if max_history_tokens is None:
        selected = list(history)
        dropped_by_token_budget = 0
    else:
        selected, dropped_by_token_budget = _limit_history_by_token_count(
            history,
            max_history_tokens,
            budget,
        )
    selected, dropped_by_message_limit = _limit_history_by_message_count(selected, budget)
    selected = drop_invalid_leading_history(selected)
    dropped = len(history) - len(selected)
    estimated_tokens = sum(
        estimate_tokens(str(message.get("content", "")), budget.chars_per_token)
        for message in selected
    )
    warnings = []
    if dropped_by_message_limit:
        warnings.append("history_trimmed")
    if dropped_by_token_budget:
        warnings.append("history_token_trimmed")
    return (
        selected,
        ContextHistoryReport(
            total_messages=len(history),
            included_messages=len(selected),
            dropped_messages=dropped,
            max_history_messages=budget.max_history_messages or 0,
            reserved_tokens=reserved_history_tokens,
            estimated_tokens=estimated_tokens,
            dropped_by_message_limit=dropped_by_message_limit,
            dropped_by_token_budget=dropped_by_token_budget,
        ),
        warnings,
    )


def combine_warnings(
    budget: ContextBudget,
    estimated_tokens_before_budget: int,
    section_warnings: list[str],
    history_warnings: list[str],
) -> list[str]:
    """Return stable report warnings without duplicates."""
    warnings: list[str] = []
    if (
        budget.max_prompt_tokens is not None
        and estimated_tokens_before_budget > budget.max_prompt_tokens
    ):
        warnings.append("context_budget_exceeded")
    for warning in [*section_warnings, *history_warnings]:
        if warning not in warnings:
            warnings.append(warning)
    return warnings


def build_report(
    *,
    current_message: InboundMessage,
    system_prompt: str,
    selected_history: list[Message],
    history_report: ContextHistoryReport,
    section_reports: list[ContextSectionReport],
    warnings: list[str],
    estimated_tokens_before_budget: int,
    budget: ContextBudget,
) -> ContextAssemblyReport:
    """Build the observable context assembly report."""
    messages: list[Message] = [
        {"role": "system", "content": system_prompt},
        *selected_history,
        {"role": "user", "content": current_message.content},
    ]
    total_chars = sum(len(str(message.get("content", ""))) for message in messages)
    return ContextAssemblyReport(
        total_chars=total_chars,
        estimated_tokens=estimate_tokens(system_prompt, budget.chars_per_token)
        + sum(
            estimate_tokens(str(message.get("content", "")), budget.chars_per_token)
            for message in selected_history
        )
        + estimate_tokens(current_message.content, budget.chars_per_token),
        estimated_tokens_before_budget=estimated_tokens_before_budget,
        max_prompt_tokens=budget.max_prompt_tokens,
        message_count=len(messages),
        sections=section_reports,
        history=history_report,
        warnings=warnings,
    )


def drop_invalid_leading_history(history: list[Message]) -> list[Message]:
    """Keep selected chat history in a valid user-starting shape."""
    selected = list(history)
    while selected and selected[0].get("role") != "user":
        selected.pop(0)
    return selected


def _limit_history_by_message_count(
    history: list[Message],
    budget: ContextBudget,
) -> tuple[list[Message], int]:
    """Apply the configured message-count history window."""
    if budget.max_history_messages is None:
        return list(history), 0
    max_messages = max(budget.max_history_messages, 0)
    dropped = max(len(history) - max_messages, 0)
    selected = history[-max_messages:] if max_messages else []
    return list(selected), dropped


def _limit_history_by_token_count(
    history: list[Message],
    max_history_tokens: int,
    budget: ContextBudget,
) -> tuple[list[Message], int]:
    """Keep the newest history messages that fit the remaining token budget."""
    selected_reversed: list[Message] = []
    used_tokens = 0
    dropped = 0
    for message in reversed(history):
        tokens = estimate_tokens(
            str(message.get("content", "")),
            budget.chars_per_token,
        )
        if used_tokens + tokens <= max_history_tokens:
            selected_reversed.append(message)
            used_tokens += tokens
        else:
            dropped += 1
    return list(reversed(selected_reversed)), dropped
