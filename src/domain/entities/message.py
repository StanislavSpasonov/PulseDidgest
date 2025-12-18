"""Domain entity representing a Telegram message stored in persistence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class MessageRecord:
    source_chat_id: int
    source_message_id: int
    date: datetime
    text: Optional[str]
