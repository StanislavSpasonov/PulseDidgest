"""Use cases for delivery outbox handling."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Protocol

from src.application.services.delivery_policy import DeliveryPolicy, compute_due_at
from src.application.services.message_formatter import (
    format_digest_from_items_html,
    format_item_html,
)
from src.application.use_cases.routing_snapshot import CategoryRoute
from src.domain.entities import DeliveryOutboxItem, DecisionRecord


class DeliveryOutboxRepository(Protocol):
    def enqueue(self, item: DeliveryOutboxItem) -> None:
        ...

    def fetch_due(self, now: datetime, limit: int = 200) -> list[DeliveryOutboxItem]:
        ...

    def mark_sent(self, ids: list[str], sent_at: datetime) -> None:
        ...

    def record_error(self, item_id: str, error_text: str) -> None:
        ...


class DecisionDeliveryRepository(Protocol):
    def mark_decision_delivered(self, decision_id: str) -> None:
        ...


class NotifierProtocol(Protocol):
    async def broadcast(self, text: str, parse_mode: str | None = None, reply_markup=None) -> bool:
        ...


class EnqueueDeliveryOutboxUseCase:
    def __init__(
        self,
        repository: DeliveryOutboxRepository,
        logger: logging.Logger | None = None,
    ) -> None:
        self._repo = repository
        self._logger = logger or logging.getLogger("collector.delivery_outbox")

    def enqueue(
        self,
        decision: DecisionRecord,
        message_text: str,
        route: CategoryRoute,
        policy: DeliveryPolicy,
        decision_id: str,
        message_id: int,
    ) -> None:
        due_at = compute_due_at(policy)
        payload = format_item_html(
            decision=decision,
            message_text=message_text,
            chat_id=route.chat_id,
            message_id=message_id,
            group_title=route.group_title,
            username=route.group_username,
        )
        item = DeliveryOutboxItem(
            id=str(uuid.uuid4()),
            user_id=None,
            decision_id=decision_id,
            category_id=route.category_id,
            category_name=route.category_name,
            chat_id=route.chat_id,
            source_message_id=message_id,
            message_text=message_text,
            score=decision.score,
            reason=decision.reason,
            group_title=route.group_title,
            group_username=route.group_username,
            payload=payload,
            due_at=due_at,
            created_at=datetime.now(timezone.utc),
            sent_at=None,
            last_error=None,
        )
        self._repo.enqueue(item)
        self._logger.info(
            "Outbox enqueued category=%s chat_id=%s due_at=%s",
            route.category_name,
            route.chat_id,
            due_at.isoformat(),
        )


class DeliveryOutboxScheduler:
    def __init__(
        self,
        repository: DeliveryOutboxRepository,
        notifier: NotifierProtocol,
        decision_repository: DecisionDeliveryRepository,
        delivery_repository=None,
        tick_seconds: int = 60,
        logger: logging.Logger | None = None,
        reply_markup_factory=None,
    ) -> None:
        self._repo = repository
        self._notifier = notifier
        self._decision_repo = decision_repository
        self._delivery_repo = delivery_repository
        self._tick_seconds = max(15, tick_seconds)
        self._logger = logger or logging.getLogger("collector.delivery_outbox")
        self._reply_markup_factory = reply_markup_factory
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self._tick()
            except Exception as exc:  # pragma: no cover
                self._logger.exception("Outbox tick failed: %s", exc)
            await asyncio.sleep(self._tick_seconds)

    async def _tick(self) -> None:
        now = datetime.now(timezone.utc)
        items = await asyncio.to_thread(self._repo.fetch_due, now)
        if not items:
            return
        groups: dict[tuple[str, int], list[DeliveryOutboxItem]] = {}
        for item in items:
            key = (item.category_id, item.chat_id)
            groups.setdefault(key, []).append(item)
        for group_items in groups.values():
            ids = [item.id for item in group_items]
            payload = format_digest_from_items_html(
                category_name=group_items[0].category_name,
                group_title=group_items[0].group_title,
                items=[item.payload for item in group_items],
            )
            reply_markup = (
                self._reply_markup_factory() if self._reply_markup_factory else None
            )
            delivered = await self._notifier.broadcast(
                payload,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
            if delivered:
                await asyncio.to_thread(self._repo.mark_sent, ids, now)
                for item in group_items:
                    await asyncio.to_thread(
                        self._decision_repo.mark_decision_delivered, item.decision_id
                    )
                if self._delivery_repo:
                    await asyncio.to_thread(
                        self._delivery_repo.update_last_sent_by_chat,
                        group_items[0].category_id,
                        group_items[0].chat_id,
                        now,
                    )
            else:
                for item in group_items:
                    await asyncio.to_thread(
                        self._repo.record_error, item.id, "delivery_failed"
                    )
