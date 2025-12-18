"""Domain entity for Telegram bot users."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class UserRecord:
    id: Optional[str]
    tg_user_id: int
    chat_id: int
    username: Optional[str]
    is_active: bool
    created_at: Optional[datetime] = None
