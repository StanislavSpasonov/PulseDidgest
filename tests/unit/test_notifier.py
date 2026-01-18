from __future__ import annotations

import pytest

from src.application.services.notifier import UserNotifier
from src.domain.entities.user import UserRecord


class FakeSender:
    def __init__(self) -> None:
        self.sent = []

    async def send_message(self, chat_id: int, text: str, parse_mode=None, reply_markup=None) -> None:
        self.sent.append((chat_id, text, parse_mode, reply_markup))

    async def close(self) -> None:
        pass


class FakeUserRepo:
    def __init__(self, admins: list[UserRecord]) -> None:
        self._admins = admins

    def list_active_admins(self) -> list[UserRecord]:
        return self._admins


def _admin(chat_id: int) -> UserRecord:
    return UserRecord(
        id=None,
        telegram_user_id=chat_id,
        chat_id=chat_id,
        username=None,
        first_name=None,
        role="admin",
        status="active",
    )


@pytest.mark.asyncio
async def test_notify_admin_sends_to_all_admins() -> None:
    sender = FakeSender()
    repo = FakeUserRepo([_admin(10), _admin(20)])
    notifier = UserNotifier(
        user_repository=repo,
        sender=sender,
        admin_chat_id=999,
    )

    await notifier.notify_admin("hello")

    assert [call[0] for call in sender.sent] == [10, 20]


@pytest.mark.asyncio
async def test_notify_admin_falls_back_to_admin_chat_id() -> None:
    sender = FakeSender()
    repo = FakeUserRepo([])
    notifier = UserNotifier(
        user_repository=repo,
        sender=sender,
        admin_chat_id=999,
    )

    await notifier.notify_admin("hello")

    assert [call[0] for call in sender.sent] == [999]
