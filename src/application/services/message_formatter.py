"""Helpers to format delivery messages with links and previews."""
from __future__ import annotations

import html
import re
from typing import Iterable, List, Optional

from src.domain.entities import DecisionRecord, PendingDecisionInfo

_URL_PATTERN = re.compile(r"(https?://[^\s<>]+|t\.me/[^\s<>]+)", re.IGNORECASE)
_TRAILING_PUNCT = ".,;:!?)]}\"'"


def build_source_link(chat_id: int, username: Optional[str], message_id: int) -> str:
    if username:
        handle = username.lstrip("@")
        return f"https://t.me/{handle}/{message_id}"
    internal = str(abs(int(chat_id)))
    if internal.startswith("100"):
        internal = internal[3:]
    return f"https://t.me/c/{internal}/{message_id}"


def extract_urls(text: str) -> List[str]:
    if not text:
        return []
    urls: List[str] = []
    for match in _URL_PATTERN.finditer(text):
        url = match.group(0)
        while url and url[-1] in _TRAILING_PUNCT:
            url = url[:-1]
        if url.lower().startswith("t.me/"):
            url = f"https://{url}"
        if url:
            urls.append(url)
    seen = set()
    unique: List[str] = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        unique.append(url)
    return unique


def build_preview(text: str, max_len: int = 600) -> str:
    if not text:
        return ""
    cleaned = _URL_PATTERN.sub("", text)
    cleaned = " ".join(cleaned.split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len].rstrip() + "…"


def _link_html(url: str, label: str) -> str:
    return f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>'


def format_item_html(
    *,
    decision: DecisionRecord,
    message_text: str,
    chat_id: int,
    message_id: int,
    group_title: Optional[str] = None,
    username: Optional[str] = None,
    preview_len: int = 600,
) -> str:
    preview = build_preview(message_text, preview_len)
    source_url = build_source_link(chat_id, username, message_id)
    urls = extract_urls(message_text)

    lines: List[str] = [
        f"<b>Score:</b> {decision.score:.2f}",
        f"<b>Reason:</b> {html.escape(decision.reason)}",
    ]
    if preview:
        lines.append(f"<b>Preview:</b> {html.escape(preview)}")
    if group_title:
        lines.append(f"<b>Source:</b> {html.escape(group_title)}")
    lines.append(f"{_link_html(source_url, '🔗 Открыть в Telegram')}")
    if not username:
        lines.append(
            f"<code>chat_id={chat_id} message_id={message_id}</code>"
        )
    if urls:
        lines.append("<b>🌐 Ссылки из текста:</b>")
        for url in urls:
            lines.append(f"• {_link_html(url, url)}")
    return "\n".join(lines)


def format_instant_message_html(
    *,
    category_name: str,
    decision: DecisionRecord,
    message_text: str,
    chat_id: int,
    message_id: int,
    group_title: Optional[str] = None,
    username: Optional[str] = None,
    preview_len: int = 600,
) -> str:
    header = f"<b>[{html.escape(category_name)}] Instant</b>"
    body = format_item_html(
        decision=decision,
        message_text=message_text,
        chat_id=chat_id,
        message_id=message_id,
        group_title=group_title,
        username=username,
        preview_len=preview_len,
    )
    return f"{header}\n{body}"


def format_digest_message_html(
    *,
    category_name: str,
    group_title: Optional[str],
    decisions: Iterable[PendingDecisionInfo],
    preview_len: int = 600,
) -> str:
    header = f"<b>[{html.escape(category_name)}] Digest</b>"
    if group_title:
        header = f"{header} <b>({html.escape(group_title)})</b>"
    blocks: List[str] = [header]
    for idx, decision in enumerate(decisions, start=1):
        item = format_item_html(
            decision=DecisionRecord(
                category_id=decision.category_id,
                model="",
                prompt_name=decision.category_name,
                prompt_version="",
                passed=True,
                score=decision.score,
                reason=decision.reason,
            ),
            message_text=decision.message_text or "",
            chat_id=decision.source_chat_id,
            message_id=decision.source_message_id,
            group_title=None,
            username=None,
            preview_len=preview_len,
        )
        blocks.append(f"<b>{idx}.</b>\n{item}")
    return "\n\n".join(blocks)
