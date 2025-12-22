"""Domain entity for delivery outbox items."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class DeliveryOutboxItem:
    id: str
    user_id: Optional[str]
    decision_id: str
    category_id: str
    category_name: str
    chat_id: int
    source_message_id: int
    message_text: Optional[str]
    score: float
    reason: str
    group_title: Optional[str]
    group_username: Optional[str]
    payload: str
    due_at: datetime
    created_at: datetime
    sent_at: Optional[datetime]
    last_error: Optional[str]
