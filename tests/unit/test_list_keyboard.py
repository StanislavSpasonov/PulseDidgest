from __future__ import annotations

from aiogram import types

from apps.bot.ui.list_keyboard import build_one_column_list, truncate


def test_truncate_adds_ellipsis() -> None:
    text = "a" * 10
    assert truncate(text, max_len=5) == "aaaa…"


def test_truncate_handles_short_text() -> None:
    assert truncate("hello", max_len=10) == "hello"


def test_build_one_column_list_layout() -> None:
    items = [1, 2, 3]
    page_obj, kb = build_one_column_list(
        items,
        label_fn=lambda value: f"Item {value}",
        callback_fn=lambda value: f"cb:{value}",
        page=0,
        page_size=2,
        page_callback_fn=lambda p: f"page:{p}",
        back_cb="back",
        home_cb="home",
    )

    assert page_obj.total == 3
    rows = kb.inline_keyboard
    assert len(rows) == 4
    assert all(len(row) == 1 for row in rows[:2])
    assert [button.text for button in rows[2]] == ["Next ➡️"]
    assert [button.text for button in rows[3]] == ["⬅️ Назад", "🏠 Домой"]


def test_build_one_column_list_with_extra_rows_keeps_nav_last() -> None:
    items = [1]
    page_obj, kb = build_one_column_list(
        items,
        label_fn=lambda value: f"Item {value}",
        callback_fn=lambda value: f"cb:{value}",
        page=0,
        page_size=1,
        page_callback_fn=None,
        back_cb="back",
        home_cb="home",
        extra_rows=[[types.InlineKeyboardButton(text="Extra", callback_data="x")]],
    )

    assert page_obj.total == 1
    rows = kb.inline_keyboard
    assert [button.text for button in rows[0]] == ["Item 1"]
    assert [button.text for button in rows[1]] == ["Extra"]
    assert [button.text for button in rows[2]] == ["⬅️ Назад", "🏠 Домой"]
