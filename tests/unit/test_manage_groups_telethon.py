from __future__ import annotations

import pytest

from src.application.use_cases.manage_groups_telethon import (
    AddGroupByNameUseCase,
    GroupNotFoundError,
    MultipleGroupsFoundError,
    SearchUserChatsUseCase,
)
from src.domain.entities import TelegramChatInfo


class FakeDialogService:
    def __init__(self, chats: list[TelegramChatInfo]) -> None:
        self._chats = chats

    async def list_user_chats(self, limit=None):
        return self._chats


class FakeAdminRepo:
    def __init__(self) -> None:
        self.registered: list[tuple[int, str | None]] = []

    def register_group(self, chat_id: int, title: str | None) -> None:
        self.registered.append((chat_id, title))


@pytest.mark.asyncio
async def test_add_group_by_exact_title() -> None:
    chats = [TelegramChatInfo(chat_id=1, title="Jobs", username=None, chat_type="group")]
    use_case = AddGroupByNameUseCase(FakeDialogService(chats), FakeAdminRepo())

    result = await use_case.execute("Jobs")

    assert result.chat_id == 1


@pytest.mark.asyncio
async def test_add_group_by_username() -> None:
    chats = [TelegramChatInfo(chat_id=2, title=None, username="jobs", chat_type="group")]
    repo = FakeAdminRepo()
    use_case = AddGroupByNameUseCase(FakeDialogService(chats), repo)

    result = await use_case.execute("@jobs")

    assert result.chat_id == 2
    assert repo.registered == [(2, "jobs")]


@pytest.mark.asyncio
async def test_add_group_raises_not_found() -> None:
    use_case = AddGroupByNameUseCase(FakeDialogService([]), FakeAdminRepo())

    with pytest.raises(GroupNotFoundError):
        await use_case.execute("missing")


@pytest.mark.asyncio
async def test_add_group_raises_multiple() -> None:
    chats = [
        TelegramChatInfo(chat_id=1, title="Jobs", username=None, chat_type="group"),
        TelegramChatInfo(chat_id=2, title="Jobs", username="jobs2", chat_type="group"),
    ]
    use_case = AddGroupByNameUseCase(FakeDialogService(chats), FakeAdminRepo())

    with pytest.raises(MultipleGroupsFoundError):
        await use_case.execute("Jobs")


@pytest.mark.asyncio
async def test_search_user_chats_matches_title_and_username() -> None:
    chats = [
        TelegramChatInfo(chat_id=1, title="Berlin Jobs", username=None, chat_type="group"),
        TelegramChatInfo(chat_id=2, title=None, username="remotejobs", chat_type="group"),
    ]
    use_case = SearchUserChatsUseCase(FakeDialogService(chats))

    result = await use_case.execute("jobs")

    assert {c.chat_id for c in result} == {1, 2}
