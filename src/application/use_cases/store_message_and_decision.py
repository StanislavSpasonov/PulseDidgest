"""Use case responsible for persisting messages and Gemini decisions."""
from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from src.domain.entities import DecisionRecord, MessageRecord


class MessageDecisionRepository(Protocol):
    """Port describing how persistence repositories should behave."""

    def save_message_and_decision(
        self,
        message: MessageRecord,
        decision: DecisionRecord,
    ) -> None:
        ...


class StoreMessageAndDecisionUseCase:
    """Stores a Telegram message and its Gemini decision in persistence."""

    def __init__(
        self,
        repository: MessageDecisionRepository,
        logger: logging.Logger | None = None,
    ) -> None:
        self._repository = repository
        self._logger = logger or logging.getLogger("collector.persistence_use_case")

    async def handle(self, message: MessageRecord, decision: DecisionRecord) -> None:
        try:
            await asyncio.to_thread(
                self._repository.save_message_and_decision,
                message,
                decision,
            )
        except Exception as exc:  # pragma: no cover - runtime guard
            self._logger.error("Failed to persist message/decision: %s", exc)
