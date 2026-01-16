from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class FeedbackMessageRecord:
    id: Optional[str]
    user_id: str
    type: str
    text: str
    status: str
    created_at: Optional[datetime] = None
