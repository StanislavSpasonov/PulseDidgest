from __future__ import annotations

from src.application.services.delivery_policy import resolve_delivery_policy
from src.application.use_cases.routing_snapshot import CategoryRoute
from src.domain.entities import PrefilterRule


def _route(**kwargs) -> CategoryRoute:
    base = dict(
        category_id="cat",
        category_name="jobs",
        prompt="p",
        debug_enabled=False,
        prefilter=PrefilterRule(min_length=1),
        group_id="g1",
        chat_id=100,
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
    base.update(kwargs)
    return CategoryRoute(**base)


def test_resolve_delivery_policy_instant() -> None:
    policy = resolve_delivery_policy(_route(delivery_mode="instant"))
    assert policy.mode == "instant"
    assert policy.schedule == "none"
    assert policy.enabled is True


def test_resolve_delivery_policy_digest() -> None:
    policy = resolve_delivery_policy(_route(delivery_mode="hourly"))
    assert policy.mode == "digest"
    assert policy.schedule == "hourly"


def test_resolve_delivery_policy_fallback_to_category_default() -> None:
    policy = resolve_delivery_policy(
        _route(delivery_mode="", category_delivery_mode="daily", category_delivery_time_local="08:00")
    )
    assert policy.mode == "digest"
    assert policy.schedule == "daily"
