"""Domain representations for categories and prefilter settings."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class PrefilterRule:
    min_length: Optional[int] = None
    include_any: List[str] = field(default_factory=list)
    exclude_any: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class RuntimeCategory:
    id: str
    name: str
    prompt: str
    is_enabled: bool
    prefilter: PrefilterRule


@dataclass(frozen=True)
class CategorySyncConfig:
    name: str
    prompt: str
    groups: List[int]
    prefilter: PrefilterRule
