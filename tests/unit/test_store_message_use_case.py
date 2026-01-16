from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.application.use_cases.store_message_and_decision import (
    StoreMessageAndDecisionUseCase,
)
from src.domain.entities import DecisionRecord, MessageRecord


class FakeRepo:
    def __init__(self) -> None:
        self.saved = []
        self.errors = []
        self.ensured = []
        self.delivered = []

    def save_message_and_decision(self, message: MessageRecord, decision: DecisionRecord) -> tuple[str, str]:
        self.saved.append((message, decision))
        return ("msg-1", "dec-1")

    def record_llm_error(self, message: MessageRecord, category_id: str, error_code: str, error_text: str) -> None:
        self.errors.append((message, category_id, error_code, error_text))

    def ensure_message(self, message: MessageRecord) -> str:
        self.ensured.append(message)
        return "msg-1"

    def mark_decision_delivered(self, decision_id: str) -> None:
        self.delivered.append(decision_id)


@pytest.mark.asyncio
async def test_store_message_and_decision_handles_save() -> None:
    repo = FakeRepo()
    use_case = StoreMessageAndDecisionUseCase(repo)
    message = MessageRecord(
        source_chat_id=1,
        source_message_id=2,
        date=datetime.now(timezone.utc),
        text="hello",
    )
    decision = DecisionRecord(
        category_id="cat-1",
        model="m",
        prompt_name="p",
        prompt_version="v",
        passed=True,
        score=0.5,
        reason="ok",
    )

    result = await use_case.handle(message, decision)

    assert result == ("msg-1", "dec-1")
    assert repo.saved


@pytest.mark.asyncio
async def test_store_message_and_decision_records_error() -> None:
    repo = FakeRepo()
    use_case = StoreMessageAndDecisionUseCase(repo)
    message = MessageRecord(
        source_chat_id=1,
        source_message_id=2,
        date=datetime.now(timezone.utc),
        text="hello",
    )

    await use_case.record_error(message, "cat-1", "ERR", "boom")

    assert repo.errors == [(message, "cat-1", "ERR", "boom")]


@pytest.mark.asyncio
async def test_store_message_and_decision_ensure_message() -> None:
    repo = FakeRepo()
    use_case = StoreMessageAndDecisionUseCase(repo)
    message = MessageRecord(
        source_chat_id=1,
        source_message_id=2,
        date=datetime.now(timezone.utc),
        text="hello",
    )

    result = await use_case.ensure_message(message)

    assert result == "msg-1"
    assert repo.ensured == [message]


@pytest.mark.asyncio
async def test_store_message_and_decision_mark_delivered() -> None:
    repo = FakeRepo()
    use_case = StoreMessageAndDecisionUseCase(repo)

    await use_case.mark_delivered("dec-1")

    assert repo.delivered == ["dec-1"]
