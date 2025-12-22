from __future__ import annotations

from src.application.use_cases.routing_snapshot import GetActiveRoutingSnapshotUseCase
from src.domain.entities import PrefilterRule, RuntimeCategoryGroup


class FakeRepo:
    def __init__(self, routes: list[RuntimeCategoryGroup]) -> None:
        self._routes = routes

    def load_active_routes(self) -> list[RuntimeCategoryGroup]:
        return self._routes


def test_get_active_routing_snapshot_groups_by_chat() -> None:
    routes = [
        RuntimeCategoryGroup(
            category_id="cat-1",
            category_name="jobs",
            prompt="p1",
            debug_enabled=False,
            prefilter=PrefilterRule(min_length=1),
            group_id="g1",
            chat_id=100,
            group_title="Chat 100",
            group_username=None,
            delivery_mode="instant",
            delivery_interval_minutes=None,
            delivery_time_local=None,
            delivery_timezone="UTC",
            last_sent_at=None,
            is_enabled=True,
            category_delivery_mode="instant",
            category_delivery_interval_minutes=None,
            category_delivery_time_local=None,
            category_delivery_timezone="UTC",
            category_delivery_enabled=True,
        ),
        RuntimeCategoryGroup(
            category_id="cat-2",
            category_name="alerts",
            prompt="p2",
            debug_enabled=True,
            prefilter=PrefilterRule(min_length=1),
            group_id="g2",
            chat_id=100,
            group_title="Chat 100",
            group_username=None,
            delivery_mode="digest",
            delivery_interval_minutes=60,
            delivery_time_local=None,
            delivery_timezone="UTC",
            last_sent_at=None,
            is_enabled=True,
            category_delivery_mode="instant",
            category_delivery_interval_minutes=None,
            category_delivery_time_local=None,
            category_delivery_timezone="UTC",
            category_delivery_enabled=True,
        ),
        RuntimeCategoryGroup(
            category_id="cat-3",
            category_name="ops",
            prompt="p3",
            debug_enabled=False,
            prefilter=PrefilterRule(min_length=1),
            group_id="g3",
            chat_id=200,
            group_title="Chat 200",
            group_username=None,
            delivery_mode="instant",
            delivery_interval_minutes=None,
            delivery_time_local=None,
            delivery_timezone="UTC",
            last_sent_at=None,
            is_enabled=True,
            category_delivery_mode="instant",
            category_delivery_interval_minutes=None,
            category_delivery_time_local=None,
            category_delivery_timezone="UTC",
            category_delivery_enabled=True,
        ),
    ]
    use_case = GetActiveRoutingSnapshotUseCase(FakeRepo(routes))

    snapshot = use_case.execute()

    assert snapshot.active_chat_ids == {100, 200}
    assert snapshot.total_bindings == 3
    assert len(snapshot.routes[100]) == 2
    assert snapshot.routes[200][0].category_name == "ops"
