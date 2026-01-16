from __future__ import annotations

from apps.bot.routers.ui_menu import build_main_menu
from src.domain.entities import UserRecord


def _user(status: str, role: str = "user") -> UserRecord:
    return UserRecord(
        id="u1",
        telegram_user_id=1,
        chat_id=1,
        username="test",
        first_name="Test",
        role=role,
        status=status,
        created_at=None,
        updated_at=None,
        last_seen_at=None,
    )


def test_pending_menu_text():
    text, _ = build_main_menu(_user("pending"), admin_user_id=1)
    assert "ожидает" in text.lower()


def test_blocked_menu_text():
    text, _ = build_main_menu(_user("blocked"), admin_user_id=1)
    assert "огранич" in text.lower()
