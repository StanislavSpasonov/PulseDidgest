from __future__ import annotations

import pytest

from src.application.use_cases.routing_snapshot import RoutingSnapshot
from src.infrastructure.collector.routing_cache import RoutingSnapshotCache


class FakeUseCase:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self) -> RoutingSnapshot:
        self.calls += 1
        if self.calls == 1:
            return RoutingSnapshot(active_chat_ids={1}, routes={1: []}, total_bindings=1)
        return RoutingSnapshot(active_chat_ids={2}, routes={2: []}, total_bindings=2)


@pytest.mark.asyncio
async def test_routing_snapshot_cache_refreshes_and_swaps() -> None:
    use_case = FakeUseCase()
    cache = RoutingSnapshotCache(use_case, refresh_seconds=5)

    await cache.refresh_once()
    first = cache.get_snapshot()

    await cache.refresh_once()
    second = cache.get_snapshot()

    assert first.active_chat_ids == {1}
    assert second.active_chat_ids == {2}
    assert use_case.calls == 2
