from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryAclEntry:
    category_id: str
    user_id: str
    permission: str
