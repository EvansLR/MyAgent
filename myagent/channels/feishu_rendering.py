"""Feishu card and text rendering helpers."""

import html
import re


def _approval_card(approval_id: str, prompt: str) -> dict:
    """Build a minimal Feishu interactive card for one approval request."""
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "orange",
            "title": {"tag": "plain_text", "content": "MyAgent 权限审批"},
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"需要你确认后才能继续执行：\n\n```text\n{_card_escape(prompt)}\n```",
                },
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "允许"},
                        "type": "primary",
                        "value": {"approval_id": approval_id, "action": "approve"},
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "拒绝"},
                        "type": "danger",
                        "value": {"approval_id": approval_id, "action": "deny"},
                    },
                ],
            },
        ],
    }


def _card_escape(text: str) -> str:
    """Keep prompt text compact inside a card code block."""
    compact = text.strip()
    if len(compact) > 1800:
        compact = compact[:1800] + "\n... (truncated)"
    return compact.replace("```", "'''")


def _render_text_message(text: str) -> tuple[str, dict]:
    """Render plain/markdown-ish text as Feishu text or post message content."""
    if _should_send_plain_text(text):
        return "text", {"text": text}
    return "post", {
        "zh_cn": {
            "title": "",
            "content": _markdown_to_post_content(text),
        }
    }


def _should_send_plain_text(text: str) -> bool:
    if len(text) > 500:
        return False
    markdown_markers = ("```", "\n#", "\n-", "\n*", "\n1.", "**", "__", "[")
    return not any(marker in text for marker in markdown_markers)


def _markdown_to_post_content(text: str) -> list[list[dict]]:
    """Convert a small Markdown subset to Feishu post rich-text paragraphs."""
    rows: list[list[dict]] = []
    in_code = False
    code_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code:
                rows.append([_text_tag("\n".join(code_lines), un_escape=True)])
                code_lines = []
                in_code = False
            else:
                if code_lines:
                    code_lines = []
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not stripped:
            rows.append([_text_tag(" ")])
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            rows.append([_text_tag(heading.group(2), bold=True)])
            continue
        bullet = re.match(r"^[-*]\s+(.+)$", stripped)
        if bullet:
            rows.append([_text_tag("- "), *_inline_tags(bullet.group(1))])
            continue
        numbered = re.match(r"^(\d+[.)])\s+(.+)$", stripped)
        if numbered:
            rows.append([_text_tag(f"{numbered.group(1)} "), *_inline_tags(numbered.group(2))])
            continue
        rows.append(_inline_tags(stripped))
    if in_code and code_lines:
        rows.append([_text_tag("\n".join(code_lines), un_escape=True)])
    return rows or [[_text_tag(text)]]


def _inline_tags(text: str) -> list[dict]:
    """Render links and bold markers for Feishu post content."""
    tags: list[dict] = []
    position = 0
    pattern = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)|\*\*([^*]+)\*\*|__([^_]+)__")
    for match in pattern.finditer(text):
        if match.start() > position:
            tags.append(_text_tag(text[position:match.start()]))
        if match.group(1) and match.group(2):
            tags.append({
                "tag": "a",
                "text": match.group(1),
                "href": match.group(2),
            })
        else:
            tags.append(_text_tag(match.group(3) or match.group(4) or "", bold=True))
        position = match.end()
    if position < len(text):
        tags.append(_text_tag(text[position:]))
    return tags or [_text_tag("")]


def _text_tag(text: str, *, bold: bool = False, un_escape: bool = False) -> dict:
    tag = {"tag": "text", "text": text}
    if bold:
        tag["style"] = ["bold"]
    if un_escape:
        tag["un_escape"] = True
        tag["text"] = html.escape(text)
    return tag
