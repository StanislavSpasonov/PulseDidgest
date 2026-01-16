from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.application.use_cases.delivery_outbox import DeliveryOutboxScheduler
from src.domain.entities import DeliveryOutboxItem


class FakeRepo:
    def __init__(self, items):
        self._items = items
        self.sent = []
        self.errors = []

    def fetch_due(self, now, limit=200):
        return self._items

    def mark_sent(self, ids, sent_at):
        self.sent.append((ids, sent_at))

    def record_error(self, item_id, error_text):
        self.errors.append((item_id, error_text))


class FakeDeliveryRepo:
    def __init__(self):
        self.calls = []

    def update_last_sent_by_chat(self, category_id, chat_id, timestamp):
        self.calls.append((category_id, chat_id, timestamp))


class FakeNotifier:
    def __init__(self, delivered=True):
        self.delivered = delivered
        self.payloads = []

    async def broadcast(self, text, parse_mode=None, reply_markup=None):
        self.payloads.append(text)
        return self.delivered


class FakeDecisionRepo:
    def __init__(self):
        self.marked = []

    def mark_decision_delivered(self, decision_id):
        self.marked.append(decision_id)


def _item(item_id: str, decision_id: str) -> DeliveryOutboxItem:
    return DeliveryOutboxItem(
        id=item_id,
        user_id=None,
        decision_id=decision_id,
        category_id="cat",
        category_name="jobs",
        chat_id=100,
        source_message_id=5,
        message_text="hello",
        score=0.9,
        reason="ok",
        group_title="Chat",
        group_username=None,
        payload="item",
        due_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        sent_at=None,
        last_error=None,
    )


@pytest.mark.asyncio
async def test_outbox_scheduler_marks_sent() -> None:
    repo = FakeRepo([_item("1", "dec-1"), _item("2", "dec-2")])
    notifier = FakeNotifier(delivered=True)
    decision_repo = FakeDecisionRepo()
    delivery_repo = FakeDeliveryRepo()
    scheduler = DeliveryOutboxScheduler(
        repo,
        notifier,
        decision_repo,
        delivery_repository=delivery_repo,
        tick_seconds=60,
    )

    await scheduler._tick()

    assert repo.sent
    assert len(decision_repo.marked) == 2
    assert delivery_repo.calls
