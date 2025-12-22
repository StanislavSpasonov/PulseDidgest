"""Delivery policy resolution for category-group bindings."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from src.application.use_cases.routing_snapshot import CategoryRoute


@dataclass(frozen=True)
class DeliveryPolicy:
    enabled: bool
    mode: str  # instant | digest
    schedule: str  # hourly | interval | daily | none
    interval_minutes: Optional[int]
    time_local: Optional[str]
    timezone: str
    source: str


def resolve_delivery_policy(route: CategoryRoute) -> DeliveryPolicy:
    delivery_mode = route.delivery_mode or route.category_delivery_mode
    mode = "instant" if delivery_mode == "instant" else "digest"
    schedule = "none" if mode == "instant" else delivery_mode
    interval = route.delivery_interval_minutes
    if interval is None:
        interval = route.category_delivery_interval_minutes
    time_local = route.delivery_time_local or route.category_delivery_time_local
    timezone_value = route.delivery_timezone or route.category_delivery_timezone
    return DeliveryPolicy(
        enabled=bool(route.is_enabled)
        if route.is_enabled is not None
        else bool(route.category_delivery_enabled),
        mode=mode,
        schedule=schedule,
        interval_minutes=interval,
        time_local=time_local,
        timezone=timezone_value,
        source="binding" if route.delivery_mode else "category",
    )


def compute_due_at(policy: DeliveryPolicy, now: Optional[datetime] = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    if policy.mode == "instant":
        return now
    schedule = policy.schedule
    if schedule == "hourly":
        return now + timedelta(hours=1)
    if schedule == "interval":
        minutes = policy.interval_minutes or 60
        return now + timedelta(minutes=max(1, minutes))
    if schedule == "daily":
        if not policy.time_local:
            return now + timedelta(days=1)
        try:
            hour, minute = [int(part) for part in policy.time_local.split(":", 1)]
        except ValueError:
            return now + timedelta(days=1)
        try:
            tz = ZoneInfo(policy.timezone)
        except Exception:
            tz = ZoneInfo("UTC")
        local_now = now.astimezone(tz)
        target = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= local_now:
            target = target + timedelta(days=1)
        return target.astimezone(timezone.utc)
    return now + timedelta(minutes=30)
