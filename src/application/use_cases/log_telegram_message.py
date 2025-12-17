"""Use case for logging incoming Telegram messages."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

try:
    from telethon.events.newmessage import NewMessage
except ModuleNotFoundError:  # pragma: no cover - avoids issues when Telethon missing locally
    NewMessage = object  # type: ignore


@dataclass
class LoggedTelegramMessage:
    chat_id: Optional[int]
    message_id: Optional[int]
    date_iso: Optional[str]
    text: str


class LogTelegramMessageUseCase:
    """Formats and logs every incoming Telegram message."""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger("collector.use_case")

    async def handle(self, event: NewMessage.Event) -> None:  # type: ignore[name-defined]
        message = getattr(event, "message", None)
        if message is None:
            self._logger.warning("Received event without message payload: %s", event)
            return

        payload = LoggedTelegramMessage(
            chat_id=getattr(event, "chat_id", None),
            message_id=getattr(message, "id", None),
            date_iso=self._format_date(getattr(message, "date", None)),
            text=getattr(message, "message", "") or "",
        )

        self._logger.info(
            "chat_id=%s message_id=%s date=%s text=%s",
            payload.chat_id,
            payload.message_id,
            payload.date_iso,
            payload.text,
        )

    @staticmethod
    def _format_date(date_obj) -> Optional[str]:
        if date_obj is None:
            return None
        try:
            return date_obj.isoformat()
        except AttributeError:
            return str(date_obj)
