"""Domain structures for delivery scheduling."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class DigestGroupInfo:
    category_id: str
    category_name: str
    group_id: str
    chat_id: int
    group_title: Optional[str]
    delivery_mode: str
    delivery_interval_minutes: Optional[int]
    delivery_time_local: Optional[str]
    delivery_timezone: str
    last_sent_at: Optional[datetime]
    is_enabled: bool


@dataclass(frozen=True)
class PendingDecisionInfo:
    decision_id: str
    category_id: str
    category_name: str
    message_text: str
    score: float
    reason: str
    created_at: datetime
