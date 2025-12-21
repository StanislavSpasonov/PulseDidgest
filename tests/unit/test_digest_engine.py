from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.application.services.digest_engine import DigestDeliveryEngine
from src.domain.entities import DigestGroupInfo


class DummyRepo:
    def fetch_digest_groups(self):
        return []

    def fetch_pending_decisions(self, category_id: str, chat_id: int, limit: int):
        return []

    def mark_decisions_delivered(self, decision_ids):
        return None

    def update_last_sent(self, category_id: str, group_id: str, timestamp: datetime):
        return None


class DummyNotifier:
    async def broadcast(self, text: str, parse_mode: str | None = None) -> bool:
        return True


def _group(**kwargs) -> DigestGroupInfo:
    base = dict(
        category_id="cat",
        category_name="jobs",
        group_id="grp",
        chat_id=1,
        group_title=None,
        delivery_mode="hourly",
        delivery_interval_minutes=None,
        delivery_time_local=None,
        delivery_timezone="UTC",
        last_sent_at=None,
        is_enabled=True,
    )
    base.update(kwargs)
    return DigestGroupInfo(**base)


def test_should_send_hourly() -> None:
    engine = DigestDeliveryEngine(DummyRepo(), DummyNotifier())
    now = datetime.now(timezone.utc)
    group = _group(delivery_mode="hourly", last_sent_at=now - timedelta(hours=2))
    assert engine._should_send(group, now) is True


def test_should_send_interval() -> None:
    engine = DigestDeliveryEngine(DummyRepo(), DummyNotifier())
    now = datetime.now(timezone.utc)
    group = _group(delivery_mode="interval", delivery_interval_minutes=30, last_sent_at=now - timedelta(minutes=20))
    assert engine._should_send(group, now) is False


def test_should_send_daily_after_time() -> None:
    engine = DigestDeliveryEngine(DummyRepo(), DummyNotifier())
    now = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    group = _group(delivery_mode="daily", delivery_time_local="08:00", delivery_timezone="UTC", last_sent_at=None)
    assert engine._should_send(group, now) is True
