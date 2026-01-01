"""Use case for delivering Gemini decisions instantly via Telegram bot."""
from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from src.application.services.message_formatter import format_instant_message_html
from src.domain.entities import DecisionRecord


class DecisionDeliveryRepository(Protocol):
    def mark_decision_delivered(self, decision_id: str) -> None:
        ...


class DeliverInstantUseCase:
    """Send pass=True decisions to all active users via Telegram."""

    def __init__(
        self,
        decision_repository: DecisionDeliveryRepository,
        notifier,
        logger: logging.Logger | None = None,
        reply_markup_factory=None,
    ) -> None:
        self._decision_repository = decision_repository
        self._notifier = notifier
        self._logger = logger or logging.getLogger("collector.delivery")
        self._reply_markup_factory = reply_markup_factory

    async def deliver(
        self,
        decision_id: str,
        decision: DecisionRecord,
        category_name: str,
        message_text: str,
        chat_id: int,
        message_id: int,
        group_title: str | None = None,
        username: str | None = None,
        recipient_chat_id: int | None = None,
        mark_delivered: bool = True,
    ) -> None:
        payload = format_instant_message_html(
            category_name=category_name,
            decision=decision,
            message_text=message_text,
            chat_id=chat_id,
            message_id=message_id,
            group_title=group_title,
            username=username,
        )
        reply_markup = (
            self._reply_markup_factory() if self._reply_markup_factory else None
        )
        if recipient_chat_id is None:
            delivered = await self._notifier.broadcast(
                payload,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
        else:
            delivered = await self._notifier.send_to_chat(
                recipient_chat_id,
                payload,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )

        if delivered and mark_delivered:
            await asyncio.to_thread(
                self._decision_repository.mark_decision_delivered,
                decision_id,
            )
        else:
            self._logger.warning(
                "Decision=%s was not delivered to any user", decision_id
            )
