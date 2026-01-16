from __future__ import annotations

from datetime import datetime, timezone

from src.application.services.delivery_policy import DeliveryPolicy
from src.application.services.user_delivery_policy import resolve_user_delivery_policy
from src.domain.entities import UserCategoryChatOverride, UserCategoryDelivery


def _base_policy() -> DeliveryPolicy:
    return DeliveryPolicy(
        enabled=True,
        mode="instant",
        schedule="none",
        interval_minutes=None,
        time_local=None,
        timezone="Europe/Berlin",
        source="binding",
        last_sent_at=None,
    )


def test_override_wins():
    base = _base_policy()
    override = UserCategoryChatOverride(
        user_id="u1",
        category_id="c1",
        chat_id=1,
        enabled=False,
        mode="digest",
        digest_kind="daily",
        interval_minutes=None,
        daily_time_hhmm="08:00",
        timezone="UTC",
        last_sent_at=datetime.now(timezone.utc),
    )
    policy = resolve_user_delivery_policy(base, None, override, is_admin=False)
    assert policy.enabled is False
    assert policy.mode == "digest"
    assert policy.schedule == "daily"


def test_default_used_when_no_override():
    base = _base_policy()
    user_delivery = UserCategoryDelivery(
        user_id="u1",
        category_id="c1",
        enabled=True,
        mode="digest",
        digest_kind="interval",
        interval_minutes=60,
        daily_time_hhmm=None,
        timezone="Europe/Berlin",
        last_sent_at=None,
    )
    policy = resolve_user_delivery_policy(base, user_delivery, None, is_admin=False)
    assert policy.enabled is True
    assert policy.mode == "digest"
    assert policy.schedule == "interval"
    assert policy.interval_minutes == 60


def test_disabled_for_non_admin_without_settings():
    base = _base_policy()
    policy = resolve_user_delivery_policy(base, None, None, is_admin=False)
    assert policy.enabled is False


def test_admin_fallback_to_base():
    base = _base_policy()
    policy = resolve_user_delivery_policy(base, None, None, is_admin=True)
    assert policy.enabled is True
    assert policy.mode == "instant"
