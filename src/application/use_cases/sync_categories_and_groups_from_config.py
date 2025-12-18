"""Sync categories/groups from YAML config into the database."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Protocol

import yaml

from src.domain.entities import (
    CategoryGroupBinding,
    CategorySyncConfig,
    DeliveryConfig,
    GroupSyncConfig,
    PrefilterRule,
)


class CategorySyncRepository(Protocol):
    def has_any_categories(self) -> bool:
        ...

    def upsert_category(
        self,
        name: str,
        prompt: str,
        debug_enabled: bool,
        prefilter: PrefilterRule,
    ) -> tuple[str, bool]:
        ...

    def upsert_source_group(self, tg_chat_id: int, title: str | None = None) -> str:
        ...

    def sync_category_groups(
        self, category_id: str, bindings: List[CategoryGroupBinding]
    ) -> None:
        ...


class SyncCategoriesAndGroupsFromConfigUseCase:
    """Loads categories.yml and syncs categories/groups according to config mode."""

    def __init__(
        self,
        repository: CategorySyncRepository,
        config_path: Path,
        config_mode: str = "seed_if_empty",
        default_tz: str = "Europe/Berlin",
        logger: logging.Logger | None = None,
    ) -> None:
        self._repo = repository
        self._config_path = config_path
        self._config_mode = config_mode
        self._default_tz = default_tz
        self._logger = logger or logging.getLogger("collector.category_sync")

    def execute(self) -> None:
        self._maybe_seed_from_config()

    def _maybe_seed_from_config(self) -> None:
        if self._config_mode.lower() == "off":
            self._logger.info("CONFIG_SYNC_MODE=off — skipping YAML sync")
            return

        try:
            has_categories = self._repo.has_any_categories()
        except Exception as exc:  # pragma: no cover
            self._logger.error("Failed to check categories presence: %s", exc)
            return

        if has_categories:
            self._logger.info("Categories already exist; YAML seed skipped")
            return

        if not self._config_path.exists():
            self._logger.warning(
                "Categories config not found; cannot seed database: %s",
                self._config_path,
            )
            return

        raw = yaml.safe_load(self._config_path.read_text()) or {}
        raw_categories = raw.get("categories", [])
        if not raw_categories:
            self._logger.warning("Categories YAML is empty; nothing to seed")
            return

        configs = [self._parse_category(entry) for entry in raw_categories]
        for cfg in configs:
            category_id, is_enabled = self._repo.upsert_category(
                cfg.name,
                cfg.prompt,
                cfg.debug_enabled,
                cfg.prefilter,
            )
            bindings: List[CategoryGroupBinding] = []
            for group_cfg in cfg.groups:
                group_db_id = self._repo.upsert_source_group(
                    group_cfg.chat_id, group_cfg.title
                )
                delivery_timezone = (
                    group_cfg.delivery.timezone or self._default_tz
                )
                bindings.append(
                    CategoryGroupBinding(
                        group_id=group_db_id,
                        chat_id=group_cfg.chat_id,
                        title=group_cfg.title,
                        delivery_mode=group_cfg.delivery.mode,
                        delivery_interval_minutes=
                            group_cfg.delivery.interval_minutes,
                        delivery_time_local=group_cfg.delivery.time_local,
                        delivery_timezone=delivery_timezone,
                        is_enabled=group_cfg.delivery.is_enabled,
                    )
                )
            self._repo.sync_category_groups(category_id, bindings)
        self._logger.info(
            "Seeded %s categories/groups from %s",
            len(configs),
            self._config_path,
        )

    def _parse_category(self, entry: dict) -> CategorySyncConfig:
        name = entry.get("name")
        prompt = entry.get("prompt")
        groups = entry.get("groups", [])
        if not name or not prompt or not groups:
            raise ValueError("Category entry must include name, prompt, groups")

        debug_enabled = bool(entry.get("debug_enabled", False))
        prefilter_entry = entry.get("prefilter", {}) or {}
        prefilter = PrefilterRule(
            min_length=prefilter_entry.get("min_length"),
            include_any=self._normalize_terms(prefilter_entry.get("include_any", [])),
            exclude_any=self._normalize_terms(prefilter_entry.get("exclude_any", [])),
        )

        parsed_groups = [self._parse_group(g) for g in groups]
        return CategorySyncConfig(
            name=name,
            prompt=str(prompt),
            debug_enabled=debug_enabled,
            groups=parsed_groups,
            prefilter=prefilter,
        )

    def _parse_group(self, value) -> GroupSyncConfig:
        if isinstance(value, dict):
            chat_id = self._parse_chat_id(value.get("chat_id"))
            delivery_entry = value.get("delivery", {}) or {}
            mode = self._normalize_mode(delivery_entry.get("mode", "instant"))
            delivery = DeliveryConfig(
                mode=mode,
                interval_minutes=delivery_entry.get("minutes"),
                time_local=delivery_entry.get("time"),
                timezone=delivery_entry.get("timezone"),
                is_enabled=delivery_entry.get("is_enabled", True),
            )
            self._validate_delivery_config(delivery)
            return GroupSyncConfig(
                chat_id=chat_id,
                title=value.get("title"),
                delivery=delivery,
            )

        chat_id = self._parse_chat_id(value)
        return GroupSyncConfig(
            chat_id=chat_id,
            title=None,
            delivery=DeliveryConfig(mode="instant"),
        )

    @staticmethod
    def _parse_chat_id(value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid chat id in config: {value}") from exc

    @staticmethod
    def _normalize_terms(values: Iterable[str]) -> List[str]:
        return [str(v).lower() for v in values if v]

    @staticmethod
    def _normalize_mode(value) -> str:
        return str(value).strip().lower()

    def _validate_delivery_config(self, delivery: DeliveryConfig) -> None:
        if delivery.mode not in {"instant", "hourly", "interval", "daily"}:
            raise ValueError(f"Unsupported delivery mode: {delivery.mode}")
        if delivery.mode == "interval" and not delivery.interval_minutes:
            raise ValueError("Interval delivery requires 'minutes'")
        if delivery.mode == "daily" and not delivery.time_local:
            raise ValueError("Daily delivery requires 'time' in HH:MM")
