"""Telethon collector service for streaming incoming messages."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Awaitable, Callable, Optional

from telethon import TelegramClient, events

from src.infrastructure.telegram.session_resolver import log_telethon_session_diagnostics

from src.application.use_cases.process_incoming_message import IncomingMessage

IncomingHandler = Callable[[IncomingMessage], Awaitable[None]]


class TelethonCollectorService:
    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_name: str,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._session_name = session_name
        self._client = TelegramClient(session_name, api_id, api_hash)
        self._logger = logger or logging.getLogger("collector.telethon")

    async def run(self, on_message: IncomingHandler, chat_filter=None) -> None:
        log_telethon_session_diagnostics(self._logger, self._session_name, "collector/use")
        @self._client.on(events.NewMessage(chats=chat_filter))
        async def _listener(event):  # type: ignore[unused-variable]
            message = getattr(event, "message", None)
            if message is None:
                return
            chat_id = getattr(event, "chat_id", None)
            message_id = getattr(message, "id", None)
            if chat_id is None or message_id is None:
                return
            try:
                chat_id_int = int(chat_id)
                message_id_int = int(message_id)
            except (TypeError, ValueError):
                return
            payload = IncomingMessage(
                chat_id=chat_id_int,
                message_id=message_id_int,
                date=getattr(message, "date", None) or datetime.utcnow(),
                text=getattr(message, "message", "") or "",
                raw_meta={
                    "sender_id": getattr(message, "sender_id", None),
                    "reply_to": getattr(message, "reply_to_msg_id", None),
                },
            )
            await on_message(payload)

        await self._client.start()
        self._logger.info("Collector started (chat_filter=%s)", chat_filter or "all")
        await self._client.run_until_disconnected()
