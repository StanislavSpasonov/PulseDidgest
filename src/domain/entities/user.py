"""Domain entity for Telegram bot users."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class UserRecord:
    id: Optional[str]
    telegram_user_id: int
    chat_id: int
    username: Optional[str]
    first_name: Optional[str]
    role: str
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
