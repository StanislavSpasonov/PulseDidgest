from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone

import pytest

from src.application.use_cases.filter_message_with_gemini import GeminiFilterDecision
from src.application.use_cases.delivery_outbox import EnqueueDeliveryOutboxUseCase
from src.application.use_cases.process_incoming_message import (
    IncomingMessage,
    ProcessIncomingMessageUseCase,
)
from src.application.use_cases.routing_snapshot import CategoryRoute, RoutingSnapshot
from src.application.use_cases.store_message_and_decision import (
    StoreMessageAndDecisionUseCase,
)
from src.domain.entities import PrefilterRule


class FakeRepo:
    def __init__(self) -> None:
        self.saved = []
        self.ensured = []
        self.errors = []

    def save_message_and_decision(self, message, decision):
        self.saved.append((message, decision))
        return ("msg-1", f"dec-{len(self.saved)}")

    def record_llm_error(self, message, category_id, error_code, error_text) -> None:
        self.errors.append((message, category_id, error_code, error_text))

    def ensure_message(self, message):
        self.ensured.append(message)
        return "msg-1"

    def mark_decision_delivered(self, decision_id: str) -> None:
        pass


class FakeInstantDelivery:
    def __init__(self) -> None:
        self.calls = []

    async def deliver(self, *args, **kwargs) -> None:
        self.calls.append((args, kwargs))


class FakeOutbox:
    def __init__(self) -> None:
        self.enqueued = []

    def enqueue(self, *args, **kwargs) -> None:
        self.enqueued.append((args, kwargs))


@dataclass
class FakeFilterUseCase:
    calls: list

    async def classify(self, message_text: str, category_name: str, category_prompt: str):
        self.calls.append((message_text, category_name, category_prompt))
        return GeminiFilterDecision(
            passed=True,
            score=0.9,
            reason="ok",
            model="m",
            prompt_name="p",
            prompt_version="v",
        )


def _route(chat_id: int, category_id: str, category_name: str) -> CategoryRoute:
    return CategoryRoute(
        category_id=category_id,
        category_name=category_name,
        prompt="prompt",
        debug_enabled=False,
        prefilter=PrefilterRule(min_length=1),
        group_id="g-1",
        chat_id=chat_id,
        group_title="Chat",
        group_username=None,
        delivery_mode="instant",
        delivery_interval_minutes=None,
        delivery_time_local=None,
        delivery_timezone="UTC",
        is_enabled=True,
        category_delivery_mode="instant",
        category_delivery_interval_minutes=None,
        category_delivery_time_local=None,
        category_delivery_timezone="UTC",
        category_delivery_enabled=True,
    )


@pytest.mark.asyncio
async def test_process_incoming_message_skips_inactive_chat() -> None:
    repo = FakeRepo()
    store_use_case = StoreMessageAndDecisionUseCase(repo)
    filter_use_case = FakeFilterUseCase([])
    process = ProcessIncomingMessageUseCase(filter_use_case, store_use_case)
    snapshot = RoutingSnapshot(active_chat_ids=set(), routes={}, total_bindings=0)
    message = IncomingMessage(
        chat_id=100,
        message_id=1,
        date=datetime.now(timezone.utc),
        text="hello",
        raw_meta={},
    )

    await process.handle(message, snapshot)

    assert filter_use_case.calls == []
    assert repo.ensured == []
    assert repo.saved == []


@pytest.mark.asyncio
async def test_process_incoming_message_calls_llm_for_each_route() -> None:
    repo = FakeRepo()
    store_use_case = StoreMessageAndDecisionUseCase(repo)
    filter_use_case = FakeFilterUseCase([])
    process = ProcessIncomingMessageUseCase(filter_use_case, store_use_case)
    snapshot = RoutingSnapshot(
        active_chat_ids={100},
        routes={
            100: [
                _route(100, "cat-1", "jobs"),
                _route(100, "cat-2", "alerts"),
            ]
        },
        total_bindings=2,
    )
    message = IncomingMessage(
        chat_id=100,
        message_id=1,
        date=datetime.now(timezone.utc),
        text="hello",
        raw_meta={},
    )

    await process.handle(message, snapshot)

    assert len(filter_use_case.calls) == 2
    assert len(repo.saved) == 2
    assert len(repo.ensured) == 1


@pytest.mark.asyncio
async def test_process_incoming_message_instant_sends() -> None:
    repo = FakeRepo()
    store_use_case = StoreMessageAndDecisionUseCase(repo)
    filter_use_case = FakeFilterUseCase([])
    instant = FakeInstantDelivery()
    process = ProcessIncomingMessageUseCase(
        filter_use_case,
        store_use_case,
        instant_delivery_use_case=instant,
    )
    snapshot = RoutingSnapshot(
        active_chat_ids={100},
        routes={100: [_route(100, "cat-1", "jobs")]},
        total_bindings=1,
    )
    message = IncomingMessage(
        chat_id=100,
        message_id=2,
        date=datetime.now(timezone.utc),
        text="hello",
        raw_meta={},
    )

    await process.handle(message, snapshot)

    assert instant.calls


@pytest.mark.asyncio
async def test_process_incoming_message_digest_enqueues() -> None:
    repo = FakeRepo()
    store_use_case = StoreMessageAndDecisionUseCase(repo)
    filter_use_case = FakeFilterUseCase([])
    outbox_repo = FakeOutbox()
    outbox_use_case = EnqueueDeliveryOutboxUseCase(outbox_repo)
    route = replace(_route(100, "cat-1", "jobs"), delivery_mode="hourly")
    process = ProcessIncomingMessageUseCase(
        filter_use_case,
        store_use_case,
        outbox_use_case=outbox_use_case,
    )
    snapshot = RoutingSnapshot(
        active_chat_ids={100},
        routes={100: [route]},
        total_bindings=1,
    )
    message = IncomingMessage(
        chat_id=100,
        message_id=2,
        date=datetime.now(timezone.utc),
        text="hello",
        raw_meta={},
    )

    await process.handle(message, snapshot)

    assert outbox_repo.enqueued
