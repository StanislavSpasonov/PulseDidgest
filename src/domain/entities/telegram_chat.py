"""Domain models for Telegram chat metadata."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TelegramChatInfo:
    chat_id: int
    title: Optional[str]
    username: Optional[str]
    chat_type: str  # e.g. "group", "channel", "supergroup"
