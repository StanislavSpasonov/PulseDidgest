from __future__ import annotations

from apps.bot.routers import ui_groups


def test_filter_my_chats_by_title() -> None:
    chats = [
        {"chat_id": 1, "title": "Berlin Jobs", "username": "berlin_jobs"},
        {"chat_id": 2, "title": "Music Club", "username": "music"},
    ]
    filtered = ui_groups._filter_my_chats(chats, "berlin")
    assert [chat["chat_id"] for chat in filtered] == [1]


def test_filter_my_chats_by_username() -> None:
    chats = [
        {"chat_id": 1, "title": "Berlin Jobs", "username": "berlin_jobs"},
        {"chat_id": 2, "title": "Music Club", "username": "music"},
    ]
    filtered = ui_groups._filter_my_chats(chats, "music")
    assert [chat["chat_id"] for chat in filtered] == [2]


def test_toggle_selected_chat() -> None:
    selected = ui_groups._toggle_selected_chat(set(), 100)
    assert selected == {100}
    selected = ui_groups._toggle_selected_chat(selected, 100)
    assert selected == set()
