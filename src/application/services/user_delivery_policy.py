from __future__ import annotations

from dataclasses import replace
from typing import Optional

from src.application.services.delivery_policy import DeliveryPolicy
from src.domain.entities import UserCategoryChatOverride, UserCategoryDelivery


def _has_override(override: UserCategoryChatOverride) -> bool:
    return any(
        value is not None
        for value in (
            override.enabled,
            override.mode,
            override.digest_kind,
            override.interval_minutes,
            override.daily_time_hhmm,
            override.timezone,
        )
    )


def _apply_settings(
    base: DeliveryPolicy,
    enabled: Optional[bool],
    mode: Optional[str],
    digest_kind: Optional[str],
    interval_minutes: Optional[int],
    daily_time_hhmm: Optional[str],
    timezone: Optional[str],
    last_sent_at,
    source: str,
) -> DeliveryPolicy:
    resolved_enabled = base.enabled if enabled is None else bool(enabled)
    resolved_mode = base.mode if not mode else mode
    if resolved_mode == "instant":
        schedule = "none"
    else:
        schedule = digest_kind or base.schedule
    return replace(
        base,
        enabled=resolved_enabled,
        mode=resolved_mode,
        schedule=schedule,
        interval_minutes=interval_minutes if interval_minutes is not None else base.interval_minutes,
        time_local=daily_time_hhmm if daily_time_hhmm else base.time_local,
        timezone=timezone if timezone else base.timezone,
        source=source,
        last_sent_at=last_sent_at if last_sent_at else base.last_sent_at,
    )


def resolve_user_delivery_policy(
    base_policy: DeliveryPolicy,
    user_delivery: UserCategoryDelivery | None,
    chat_override: UserCategoryChatOverride | None,
    is_admin: bool,
) -> DeliveryPolicy:
    if chat_override and _has_override(chat_override):
        return _apply_settings(
            base_policy,
            chat_override.enabled,
            chat_override.mode,
            chat_override.digest_kind,
            chat_override.interval_minutes,
            chat_override.daily_time_hhmm,
            chat_override.timezone,
            chat_override.last_sent_at,
            "override",
        )

    if user_delivery:
        return _apply_settings(
            base_policy,
            user_delivery.enabled,
            user_delivery.mode,
            user_delivery.digest_kind,
            user_delivery.interval_minutes,
            user_delivery.daily_time_hhmm,
            user_delivery.timezone,
            user_delivery.last_sent_at,
            "user",
        )

    if is_admin:
        return replace(base_policy, source="global")

    return replace(base_policy, enabled=False, source="disabled")
