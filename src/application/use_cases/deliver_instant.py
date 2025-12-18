"""Use case for delivering Gemini decisions instantly via Telegram bot."""
from __future__ import annotations

import asyncio
import logging
from typing import Protocol

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
    ) -> None:
        self._decision_repository = decision_repository
        self._notifier = notifier
        self._logger = logger or logging.getLogger("collector.delivery")

    async def deliver(
        self,
        decision_id: str,
        decision: DecisionRecord,
        category_name: str,
        message_text: str,
        group_title: str | None = None,
    ) -> None:
        payload = self._build_message(
            decision, category_name, message_text, group_title
        )
        delivered = await self._notifier.broadcast(payload)

        if delivered:
            await asyncio.to_thread(
                self._decision_repository.mark_decision_delivered,
                decision_id,
            )
        else:
            self._logger.warning(
                "Decision=%s was not delivered to any user", decision_id
            )

    def _build_message(
        self,
        decision: DecisionRecord,
        category_name: str,
        message_text: str,
        group_title: str | None,
    ) -> str:
        status = "✅ PASS" if decision.passed else "❌ FAIL"
        group_label = f" ({group_title})" if group_title else ""
        return (
            f"[{category_name}{group_label}] {status}\n"
            f"Score: {decision.score:.2f}\nReason: {decision.reason}\n\n"
            f"{message_text}"
        )
