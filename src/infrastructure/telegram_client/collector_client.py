"""Telegram client wrapper dedicated to the collector MVP."""
from __future__ import annotations

import logging
from typing import Awaitable, Callable, Optional

from telethon import TelegramClient, events

MessageHandler = Callable[[events.NewMessage.Event], Awaitable[None]]


class TelegramCollectorClient:
    """Thin wrapper that wires Telethon events to an async handler."""

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_name: str,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._client = TelegramClient(session_name, api_id, api_hash)
        self._logger = logger or logging.getLogger("collector.telegram_client")

    async def run(self, source_chat: str, on_message: MessageHandler) -> None:
        """Start listening to a single source chat and forward events to handler."""

        @self._client.on(events.NewMessage(chats=source_chat))
        async def _listener(event):  # type: ignore[unused-variable]
            await on_message(event)

        self._logger.info("Connecting to Telegram. Listening to chat: %s", source_chat)
        await self._client.start()
        self._logger.info("Collector is now running (Ctrl+C to stop).")
        await self._client.run_until_disconnected()
