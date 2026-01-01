from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class UserCategoryDelivery:
    user_id: str
    category_id: str
    enabled: bool
    mode: str
    digest_kind: Optional[str]
    interval_minutes: Optional[int]
    daily_time_hhmm: Optional[str]
    timezone: str
    last_sent_at: Optional[datetime]


@dataclass(frozen=True)
class UserCategoryChatOverride:
    user_id: str
    category_id: str
    chat_id: int
    enabled: Optional[bool]
    mode: Optional[str]
    digest_kind: Optional[str]
    interval_minutes: Optional[int]
    daily_time_hhmm: Optional[str]
    timezone: Optional[str]
    last_sent_at: Optional[datetime]
