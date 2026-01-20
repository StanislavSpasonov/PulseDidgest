from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging

import pytest

from src.infrastructure.telegram_client.collector_service import TelethonCollectorService


@dataclass
class FakeMessage:
    id: int | None
    message: str
    date: datetime


@dataclass
class FakeEvent:
    chat_id: int | str | None
    message: FakeMessage | None


class FakeClient:
    def __init__(self, events: list[FakeEvent]) -> None:
        self._events = events
        self._handler = None

    def on(self, *_args, **_kwargs):
        def decorator(handler):
            self._handler = handler
            return handler

        return decorator

    async def start(self) -> None:
        return None

    async def run_until_disconnected(self) -> None:
        if not self._handler:
            return
        for event in self._events:
            await self._handler(event)


@pytest.mark.asyncio
async def test_collector_dispatches_valid_message() -> None:
    events = [
        FakeEvent(
            chat_id=100,
            message=FakeMessage(
                id=200,
                message="hello",
                date=datetime.now(timezone.utc),
            ),
        )
    ]
    client = FakeClient(events)
    service = TelethonCollectorService.__new__(TelethonCollectorService)
    service._session_name = "test-session"
    service._client = client
    service._logger = logging.getLogger("test.collector")
    received = []

    async def on_message(payload):
        received.append(payload)

    await service.run(on_message)

    assert len(received) == 1
    assert received[0].chat_id == 100
    assert received[0].message_id == 200
    assert received[0].text == "hello"


@pytest.mark.asyncio
async def test_collector_skips_invalid_message() -> None:
    events = [
        FakeEvent(chat_id=None, message=None),
        FakeEvent(
            chat_id="not-int",
            message=FakeMessage(
                id=200,
                message="bad chat id",
                date=datetime.now(timezone.utc),
            ),
        ),
        FakeEvent(
            chat_id=100,
            message=FakeMessage(
                id=None,
                message="missing id",
                date=datetime.now(timezone.utc),
            ),
        ),
    ]
    client = FakeClient(events)
    service = TelethonCollectorService.__new__(TelethonCollectorService)
    service._session_name = "test-session"
    service._client = client
    service._logger = logging.getLogger("test.collector")
    received = []

    async def on_message(payload):
        received.append(payload)

    await service.run(on_message)

    assert received == []
