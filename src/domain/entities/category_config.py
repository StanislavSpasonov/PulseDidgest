"""Domain representations for categories and prefilter settings."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
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
    debug_enabled: bool


@dataclass(frozen=True)
class RuntimeCategoryGroup:
    category_id: str
    category_name: str
    prompt: str
    debug_enabled: bool
    prefilter: PrefilterRule
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
class DeliveryConfig:
    mode: str = "instant"
    interval_minutes: Optional[int] = None
    time_local: Optional[str] = None
    timezone: Optional[str] = None
    is_enabled: bool = True


@dataclass(frozen=True)
class GroupSyncConfig:
    chat_id: int
    title: Optional[str]
    delivery: DeliveryConfig


@dataclass(frozen=True)
class CategoryGroupBinding:
    group_id: str
    chat_id: int
    title: Optional[str]
    delivery_mode: str
    delivery_interval_minutes: Optional[int]
    delivery_time_local: Optional[str]
    delivery_timezone: str
    is_enabled: bool


@dataclass(frozen=True)
class CategorySyncConfig:
    name: str
    prompt: str
    debug_enabled: bool
    groups: List[GroupSyncConfig]
    prefilter: PrefilterRule
