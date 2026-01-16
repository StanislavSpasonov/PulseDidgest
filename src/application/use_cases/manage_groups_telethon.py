"""Use cases for managing groups via Telethon dialogs."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional

from src.domain.entities import TelegramChatInfo


class GroupLookupError(Exception):
    """Base class for group lookup failures."""


class GroupNotFoundError(GroupLookupError):
    def __init__(self, query: str) -> None:
        super().__init__(f"No chat found for '{query}'")
        self.query = query


@dataclass
class MultipleGroupsFoundError(GroupLookupError):
    matches: List[TelegramChatInfo]

    def __str__(self) -> str:  # pragma: no cover - string formatting only
        return "Multiple groups found"


class ListUserChatsUseCase:
    def __init__(self, dialog_service, logger: Optional[logging.Logger] = None) -> None:
        self._dialog_service = dialog_service
        self._logger = logger or logging.getLogger("bot.list_chats")

    async def execute(self, limit: Optional[int] = None) -> List[TelegramChatInfo]:
        chats = await self._dialog_service.list_user_chats(limit=limit)
        self._logger.debug("list_user_chats fetched=%s", len(chats))
        return chats


class SearchUserChatsUseCase:
    def __init__(self, dialog_service, logger: Optional[logging.Logger] = None) -> None:
        self._dialog_service = dialog_service
        self._logger = logger or logging.getLogger("bot.search_chats")

    async def execute(self, query: str, limit: Optional[int] = None) -> List[TelegramChatInfo]:
        normalized = query.strip().lower()
        if not normalized:
            return []
        chats = await self._dialog_service.list_user_chats(limit=limit)
        matches = [
            chat
            for chat in chats
            if (chat.title and normalized in chat.title.lower())
            or (chat.username and normalized in chat.username.lower())
        ]
        self._logger.debug("search_user_chats matches=%s query=%s", len(matches), query)
        return matches


class AddGroupByNameUseCase:
    def __init__(
        self,
        dialog_service,
        admin_repository,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._dialog_service = dialog_service
        self._admin_repository = admin_repository
        self._logger = logger or logging.getLogger("bot.add_group")

    async def execute(self, query: str) -> TelegramChatInfo:
        normalized_query = query.strip()
        if not normalized_query:
            raise GroupNotFoundError(query)

        chats = await self._dialog_service.list_user_chats()
        matches = self._match_chats(chats, normalized_query)
        if not matches:
            raise GroupNotFoundError(query)
        if len(matches) > 1:
            raise MultipleGroupsFoundError(matches=matches)

        chat = matches[0]
        await asyncio.to_thread(
            self._admin_repository.register_group,
            chat.chat_id,
            chat.title or chat.username,
            chat.username,
        )
        self._logger.info(
            "Registered group %s chat_id=%s via query '%s'",
            chat.title or chat.username,
            chat.chat_id,
            query,
        )
        return chat

    def _match_chats(
        self, chats: List[TelegramChatInfo], query: str
    ) -> List[TelegramChatInfo]:
        username_candidate = self._normalize_username(query)
        if username_candidate:
            matches = [
                chat
                for chat in chats
                if chat.username and chat.username.lower() == username_candidate
            ]
            if matches:
                return matches

        title_candidate = query.strip().lower()
        matches = [
            chat
            for chat in chats
            if chat.title and chat.title.lower() == title_candidate
        ]
        return matches

    @staticmethod
    def _normalize_username(value: str) -> Optional[str]:
        candidate = value.strip().lower()
        if candidate.startswith("https://") or candidate.startswith("http://"):
            candidate = candidate.split("/", 3)[-1]
        if candidate.startswith("t.me/"):
            candidate = candidate.split("/", 1)[1]
        if candidate.startswith("@"):
            candidate = candidate[1:]
        candidate = candidate.strip()
        return candidate if candidate else None
