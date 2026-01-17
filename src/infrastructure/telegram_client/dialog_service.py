"""Telethon dialogs service for listing user chats."""
from __future__ import annotations

import logging
from typing import List, Optional

from telethon import TelegramClient
from telethon.tl.types import Channel, Chat
from telethon.utils import get_peer_id

from src.domain.entities import TelegramChatInfo


class TelethonDialogService:
    """Provides access to the user's chats via Telethon session."""

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_name: str,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        self._session_name = session_name
        self._logger = logger or logging.getLogger("telethon.dialogs")

    async def list_user_chats(self, limit: Optional[int] = None) -> List[TelegramChatInfo]:
        client = TelegramClient(self._session_name, self._api_id, self._api_hash)
        await client.connect()
        try:
            if not await client.is_user_authorized():
                raise TelethonUnauthorizedError(
                    "Telethon session is not authorized. Run the collector once to authenticate."
                )
            dialogs = await client.get_dialogs(limit=limit)
            chats: List[TelegramChatInfo] = []
            for dialog in dialogs:
                entity = dialog.entity
                chat_type = None
                if isinstance(entity, Channel):
                    chat_type = "channel" if entity.broadcast else "supergroup"
                elif isinstance(entity, Chat):
                    chat_type = "group"
                if not chat_type:
                    continue
                chat_id = get_peer_id(entity)
                chats.append(
                    TelegramChatInfo(
                        chat_id=chat_id,
                        title=getattr(entity, "title", None),
                        username=(getattr(entity, "username", None) or None),
                        chat_type=chat_type,
                    )
                )
            chats.sort(key=lambda c: (c.title or c.username or str(c.chat_id)).lower())
            self._logger.debug("Fetched %s chats via Telethon", len(chats))
            return chats
        finally:
            await client.disconnect()


class TelethonUnauthorizedError(RuntimeError):
    """Raised when the Telethon session is missing or not authorized."""
