"""Sync categories/groups from YAML config into the database."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Protocol

import yaml

from src.domain.entities import CategorySyncConfig, PrefilterRule, RuntimeCategory


class CategorySyncRepository(Protocol):
    def upsert_category(
        self, name: str, prompt: str, is_enabled: bool = True
    ) -> tuple[str, bool]:
        ...

    def upsert_source_group(self, tg_chat_id: int, title: str | None = None) -> str:
        ...

    def sync_category_groups(self, category_id: str, group_ids: List[str]) -> None:
        ...


@dataclass
class CategoryRegistry:
    chat_to_categories: Dict[int, List[RuntimeCategory]]

    def get_categories_for_chat(self, chat_id: int) -> List[RuntimeCategory]:
        return self.chat_to_categories.get(chat_id, [])


class SyncCategoriesAndGroupsFromConfigUseCase:
    """Loads categories.yml and syncs categories and groups in DB."""

    def __init__(
        self,
        repository: CategorySyncRepository,
        config_path: Path,
        logger: logging.Logger | None = None,
    ) -> None:
        self._repo = repository
        self._config_path = config_path
        self._logger = logger or logging.getLogger("collector.category_sync")

    def execute(self) -> CategoryRegistry:
        if not self._config_path.exists():
            self._logger.warning("Categories config not found: %s", self._config_path)
            return CategoryRegistry(chat_to_categories={})

        raw = yaml.safe_load(self._config_path.read_text()) or {}
        raw_categories = raw.get("categories", [])
        configs = [self._parse_category(entry) for entry in raw_categories]

        chat_to_categories: Dict[int, List[RuntimeCategory]] = {}
        for cfg in configs:
            category_id, is_enabled = self._repo.upsert_category(
                cfg.name, cfg.prompt, True
            )
            group_ids: List[str] = []
            for chat_id in cfg.groups:
                group_db_id = self._repo.upsert_source_group(chat_id)
                group_ids.append(group_db_id)
                runtime = RuntimeCategory(
                    id=category_id,
                    name=cfg.name,
                    prompt=cfg.prompt,
                    is_enabled=is_enabled,
                    prefilter=cfg.prefilter,
                )
                chat_to_categories.setdefault(chat_id, []).append(runtime)
            self._repo.sync_category_groups(category_id, group_ids)

        return CategoryRegistry(chat_to_categories=chat_to_categories)

    def _parse_category(self, entry: dict) -> CategorySyncConfig:
        name = entry.get("name")
        prompt = entry.get("prompt")
        groups = entry.get("groups", [])
        if not name or not prompt or not groups:
            raise ValueError("Category entry must include name, prompt, groups")

        parsed_groups = [self._parse_chat_id(value) for value in groups]
        prefilter_entry = entry.get("prefilter", {}) or {}
        prefilter = PrefilterRule(
            min_length=prefilter_entry.get("min_length"),
            include_any=self._normalize_terms(prefilter_entry.get("include_any", [])),
            exclude_any=self._normalize_terms(prefilter_entry.get("exclude_any", [])),
        )
        return CategorySyncConfig(
            name=name,
            prompt=str(prompt),
            groups=parsed_groups,
            prefilter=prefilter,
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
