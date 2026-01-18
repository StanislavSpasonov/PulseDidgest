"""User notification utilities for Telegram delivery."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from collections import defaultdict, deque
from datetime import datetime, timedelta


class TelegramSenderProtocol:
    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str | None = None,
        reply_markup=None,
    ) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


class UserNotifier:
    """Broadcasts messages to registered users and admins."""

    def __init__(
        self,
        user_repository,
        sender: TelegramSenderProtocol,
        admin_chat_id: Optional[int] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._user_repository = user_repository
        self._sender = sender
        self._admin_chat_id = admin_chat_id
        self._logger = logger or logging.getLogger("collector.notifier")

    async def broadcast(
        self,
        text: str,
        parse_mode: str | None = None,
        reply_markup=None,
    ) -> bool:
        users = await asyncio.to_thread(self._user_repository.get_active_users)
        if not users:
            self._logger.info("No active users to broadcast message")
            return False

        delivered = False
        for user in users:
            try:
                await self._sender.send_message(
                    user.chat_id,
                    text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                )
                delivered = True
            except Exception as exc:  # pragma: no cover
                self._logger.warning(
                    "Failed to send message to chat_id=%s: %s",
                    user.chat_id,
                    exc,
                )
        return delivered

    async def send_to_chat(
        self,
        chat_id: int,
        text: str,
        parse_mode: str | None = None,
        reply_markup=None,
    ) -> bool:
        try:
            await self._sender.send_message(
                chat_id,
                text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
            return True
        except Exception as exc:  # pragma: no cover
            self._logger.warning("Failed to send message to chat_id=%s: %s", chat_id, exc)
            return False
    async def notify_admin(
        self,
        text: str,
        parse_mode: str | None = None,
        reply_markup=None,
    ) -> None:
        admin_users = []
        if self._user_repository:
            admin_users = await asyncio.to_thread(self._user_repository.list_active_admins)
        if not admin_users and not self._admin_chat_id:
            return
        for admin in admin_users:
            try:
                await self._sender.send_message(
                    admin.chat_id,
                    text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                )
            except Exception as exc:  # pragma: no cover
                self._logger.warning(
                    "Failed to send admin notification to chat_id=%s: %s",
                    admin.chat_id,
                    exc,
                )
        if not admin_users and self._admin_chat_id:
            try:
                await self._sender.send_message(
                    self._admin_chat_id,
                    text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                )
            except Exception as exc:  # pragma: no cover
                self._logger.warning("Failed to send admin notification: %s", exc)


class DebugThrottle:
    """Limits debug notifications per category to avoid flooding."""

    def __init__(self, max_per_minute: int = 20) -> None:
        self._max_per_minute = max_per_minute
        self._events: dict[str, deque[datetime]] = defaultdict(deque)
        self._last_warning: dict[str, datetime] = {}

    def check(self, category_id: str) -> tuple[bool, bool]:
        now = datetime.utcnow()
        window = now - timedelta(minutes=1)
        dq = self._events[category_id]
        while dq and dq[0] < window:
            dq.popleft()

        if len(dq) < self._max_per_minute:
            dq.append(now)
            return True, False

        last_warn = self._last_warning.get(category_id)
        if not last_warn or now - last_warn >= timedelta(minutes=1):
            self._last_warning[category_id] = now
            return False, True
        return False, False
