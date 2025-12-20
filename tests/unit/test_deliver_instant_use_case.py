from __future__ import annotations

import pytest

from src.application.use_cases.deliver_instant import DeliverInstantUseCase
from src.domain.entities import DecisionRecord


class FakeNotifier:
    def __init__(self, delivered: bool) -> None:
        self._delivered = delivered
        self.payloads: list[str] = []

    async def broadcast(self, text: str) -> bool:
        self.payloads.append(text)
        return self._delivered


class FakeRepo:
    def __init__(self) -> None:
        self.marked: list[str] = []

    def mark_decision_delivered(self, decision_id: str) -> None:
        self.marked.append(decision_id)


@pytest.mark.asyncio
async def test_deliver_marks_decision_when_delivered() -> None:
    notifier = FakeNotifier(delivered=True)
    repo = FakeRepo()
    use_case = DeliverInstantUseCase(repo, notifier)
    decision = DecisionRecord(
        category_id="cat",
        model="m",
        prompt_name="p",
        prompt_version="v",
        passed=True,
        score=0.7,
        reason="ok",
    )

    await use_case.deliver("dec-1", decision, "jobs", "hello", "Group")

    assert repo.marked == ["dec-1"]
    assert notifier.payloads


@pytest.mark.asyncio
async def test_deliver_skips_mark_when_not_delivered() -> None:
    notifier = FakeNotifier(delivered=False)
    repo = FakeRepo()
    use_case = DeliverInstantUseCase(repo, notifier)
    decision = DecisionRecord(
        category_id="cat",
        model="m",
        prompt_name="p",
        prompt_version="v",
        passed=True,
        score=0.7,
        reason="ok",
    )

    await use_case.deliver("dec-1", decision, "jobs", "hello", None)

    assert repo.marked == []
