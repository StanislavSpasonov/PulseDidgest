from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import List, Sequence, Tuple, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class Page:
    items: List[T]
    page: int
    per_page: int
    total: int

    @property
    def total_pages(self) -> int:
        return max(1, ceil(self.total / self.per_page))

    @property
    def has_prev(self) -> bool:
        return self.page > 0

    @property
    def has_next(self) -> bool:
        return self.page + 1 < self.total_pages


def paginate(items: Sequence[T], page: int, per_page: int) -> Page:
    total = len(items)
    safe_page = max(0, page)
    if total == 0:
        return Page(items=[], page=0, per_page=per_page, total=0)
    start = safe_page * per_page
    end = start + per_page
    return Page(items=list(items[start:end]), page=safe_page, per_page=per_page, total=total)


def page_bounds(page: int, total_pages: int) -> Tuple[int, int]:
    prev_page = max(0, page - 1)
    next_page = min(total_pages - 1, page + 1)
    return prev_page, next_page
