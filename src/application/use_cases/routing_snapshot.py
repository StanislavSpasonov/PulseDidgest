"""Routing snapshot use case for dynamic collector routing."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Protocol, Set

from src.domain.entities import PrefilterRule, RuntimeCategoryGroup


@dataclass(frozen=True)
class CategoryRoute:
    category_id: str
    category_name: str
    prompt: str
    debug_enabled: bool
    prefilter: PrefilterRule
    group_id: str
    chat_id: int
    group_title: str | None
    group_username: str | None
    delivery_mode: str
    delivery_interval_minutes: int | None
    delivery_time_local: str | None
    delivery_timezone: str
    is_enabled: bool
    category_delivery_mode: str
    category_delivery_interval_minutes: int | None
    category_delivery_time_local: str | None
    category_delivery_timezone: str
    category_delivery_enabled: bool


@dataclass(frozen=True)
class RoutingSnapshot:
    active_chat_ids: Set[int]
    routes: Dict[int, List[CategoryRoute]]
    total_bindings: int

    @classmethod
    def empty(cls) -> "RoutingSnapshot":
        return cls(active_chat_ids=set(), routes={}, total_bindings=0)


class RoutingSnapshotRepository(Protocol):
    def load_active_routes(self) -> List[RuntimeCategoryGroup]:
        ...


class GetActiveRoutingSnapshotUseCase:
    def __init__(
        self,
        repository: RoutingSnapshotRepository,
        logger: logging.Logger | None = None,
    ) -> None:
        self._repo = repository
        self._logger = logger or logging.getLogger("collector.routing_snapshot")

    def execute(self) -> RoutingSnapshot:
        routes = self._repo.load_active_routes()
        mapping: Dict[int, List[CategoryRoute]] = {}
        for route in routes:
            item = CategoryRoute(
                category_id=route.category_id,
                category_name=route.category_name,
                prompt=route.prompt,
                debug_enabled=route.debug_enabled,
                prefilter=route.prefilter,
                group_id=route.group_id,
                chat_id=route.chat_id,
                group_title=route.group_title,
                group_username=route.group_username,
                delivery_mode=route.delivery_mode,
                delivery_interval_minutes=route.delivery_interval_minutes,
                delivery_time_local=route.delivery_time_local,
                delivery_timezone=route.delivery_timezone,
                is_enabled=route.is_enabled,
                category_delivery_mode=route.category_delivery_mode,
                category_delivery_interval_minutes=route.category_delivery_interval_minutes,
                category_delivery_time_local=route.category_delivery_time_local,
                category_delivery_timezone=route.category_delivery_timezone,
                category_delivery_enabled=route.category_delivery_enabled,
            )
            mapping.setdefault(route.chat_id, []).append(item)

        active_chat_ids = set(mapping.keys())
        snapshot = RoutingSnapshot(
            active_chat_ids=active_chat_ids,
            routes=mapping,
            total_bindings=len(routes),
        )
        self._logger.debug(
            "Routing snapshot: chats=%s bindings=%s",
            len(active_chat_ids),
            snapshot.total_bindings,
        )
        return snapshot
