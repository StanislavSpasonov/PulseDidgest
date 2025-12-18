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
    ) -> tuple[str, str]:
        ...

    def record_llm_error(
        self,
        message: MessageRecord,
        category_id: str,
        error_code: str,
        error_text: str,
    ) -> None:
        ...

    def ensure_message(self, message: MessageRecord) -> str:
        ...

    def mark_decision_delivered(self, decision_id: str) -> None:
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

    async def handle(
        self, message: MessageRecord, decision: DecisionRecord
    ) -> tuple[str, str] | None:
        try:
            return await asyncio.to_thread(
                self._repository.save_message_and_decision,
                message,
                decision,
            )
        except Exception as exc:  # pragma: no cover - runtime guard
            self._logger.error("Failed to persist message/decision: %s", exc)
            return None

    async def record_error(
        self, message: MessageRecord, category_id: str, code: str, text: str
    ) -> None:
        try:
            await asyncio.to_thread(
                self._repository.record_llm_error,
                message,
                category_id,
                code,
                text,
            )
        except Exception as exc:  # pragma: no cover
            self._logger.error("Failed to persist llm error: %s", exc)

    async def ensure_message(self, message: MessageRecord) -> str | None:
        try:
            return await asyncio.to_thread(self._repository.ensure_message, message)
        except Exception as exc:  # pragma: no cover
            self._logger.error("Failed to ensure message record: %s", exc)
            return None

    async def mark_delivered(self, decision_id: str) -> None:
        try:
            await asyncio.to_thread(
                self._repository.mark_decision_delivered, decision_id
            )
        except Exception as exc:  # pragma: no cover
            self._logger.error("Failed to mark decision delivered: %s", exc)
