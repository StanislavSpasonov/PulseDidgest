from __future__ import annotations

from src.application.services.message_formatter import (
    build_source_link,
    extract_urls,
    format_item_html,
)
from src.domain.entities import DecisionRecord


def test_build_source_link_with_username() -> None:
    url = build_source_link(-100123, "channel", 42)
    assert url == "https://t.me/channel/42"


def test_build_source_link_private_chat() -> None:
    url = build_source_link(-1001234567890, None, 99)
    assert url == "https://t.me/c/1234567890/99"


def test_extract_urls_collects_and_normalizes() -> None:
    text = "See https://example.com/path and t.me/test/1."
    urls = extract_urls(text)
    assert urls == ["https://example.com/path", "https://t.me/test/1"]


def test_format_item_html_escapes_text() -> None:
    decision = DecisionRecord(
        category_id="cat",
        model="m",
        prompt_name="p",
        prompt_version="v",
        passed=True,
        score=0.8,
        reason="Rock & Roll",
    )
    html = format_item_html(
        decision=decision,
        message_text="Hello <b>world</b>",
        chat_id=-100123,
        message_id=5,
    )
    assert "Rock &amp; Roll" in html
    assert "Hello &lt;b&gt;world&lt;/b&gt;" in html
