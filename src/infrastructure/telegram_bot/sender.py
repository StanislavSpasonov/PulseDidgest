"""Simple Telegram bot sender using aiogram Bot API."""
from __future__ import annotations

from aiogram import Bot


class TelegramBotSender:
    """Wraps aiogram Bot to send messages from the collector."""

    def __init__(self, token: str) -> None:
        self._bot = Bot(token=token)

    async def send_message(
        self, chat_id: int, text: str, parse_mode: str | None = None
    ) -> None:
        await self._bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
        )

    async def close(self) -> None:
        await self._bot.session.close()
