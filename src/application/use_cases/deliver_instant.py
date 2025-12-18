"""Use case for delivering Gemini decisions instantly via Telegram bot."""
from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from src.domain.entities import DecisionRecord, UserRecord


class UserRepository(Protocol):
    def get_active_users(self) -> list[UserRecord]:
        ...


class DecisionDeliveryRepository(Protocol):
    def mark_decision_delivered(self, decision_id: str) -> None:
        ...


class TelegramDeliverySender(Protocol):
    async def send_message(self, chat_id: int, text: str) -> None:
        ...


class DeliverInstantUseCase:
    """Send pass=True decisions to all active users via Telegram."""

    def __init__(
        self,
        user_repository: UserRepository,
        decision_repository: DecisionDeliveryRepository,
        sender: TelegramDeliverySender,
        logger: logging.Logger | None = None,
    ) -> None:
        self._user_repository = user_repository
        self._decision_repository = decision_repository
        self._sender = sender
        self._logger = logger or logging.getLogger("collector.delivery")

    async def deliver(
        self,
        decision_id: str,
        decision: DecisionRecord,
        category_name: str,
        message_text: str,
    ) -> None:
        try:
            users = await asyncio.to_thread(self._user_repository.get_active_users)
        except Exception as exc:  # pragma: no cover
            self._logger.error("Failed to load users: %s", exc)
            return

        if not users:
            self._logger.info("No active users to deliver decision=%s", decision_id)
            return

        payload = self._build_message(decision, category_name, message_text)
        delivered = False
        for user in users:
            try:
                await self._sender.send_message(user.chat_id, payload)
                delivered = True
            except Exception as exc:  # pragma: no cover
                self._logger.warning(
                    "Failed to deliver to user chat_id=%s: %s",
                    user.chat_id,
                    exc,
                )

        if delivered:
            await asyncio.to_thread(
                self._decision_repository.mark_decision_delivered,
                decision_id,
            )
            self._logger.info(
                "Decision=%s delivered to %d user(s)", decision_id, len(users)
            )
        else:
            self._logger.warning(
                "Decision=%s was not delivered to any user", decision_id
            )

    def _build_message(
        self, decision: DecisionRecord, category_name: str, message_text: str
    ) -> str:
        status = "✅ PASS" if decision.passed else "❌ FAIL"
        return (
            f"[{category_name}] {status}\n"
            f"Score: {decision.score:.2f}\nReason: {decision.reason}\n\n"
            f"{message_text}"
        )
