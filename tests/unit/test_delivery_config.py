from __future__ import annotations

from pathlib import Path

import pytest

from src.application.use_cases.sync_categories_and_groups_from_config import (
    SyncCategoriesAndGroupsFromConfigUseCase,
)


class DummyRepo:
    def has_any_categories(self) -> bool:
        return True

    def upsert_category(self, name: str, prompt: str, debug_enabled: bool, prefilter):
        raise NotImplementedError

    def upsert_source_group(self, tg_chat_id: int, title: str | None = None) -> str:
        raise NotImplementedError

    def sync_category_groups(self, category_id: str, bindings) -> None:
        raise NotImplementedError

    def load_runtime_registry(self):
        return {}


def _use_case() -> SyncCategoriesAndGroupsFromConfigUseCase:
    return SyncCategoriesAndGroupsFromConfigUseCase(
        repository=DummyRepo(),
        config_path=Path("unused.yml"),
    )


def test_validate_delivery_config_invalid_mode() -> None:
    use_case = _use_case()
    with pytest.raises(ValueError):
        use_case._parse_group({"chat_id": 1, "delivery": {"mode": "weekly"}})


def test_validate_delivery_config_missing_interval_minutes() -> None:
    use_case = _use_case()
    with pytest.raises(ValueError):
        use_case._parse_group({"chat_id": 1, "delivery": {"mode": "interval"}})


def test_validate_delivery_config_missing_daily_time() -> None:
    use_case = _use_case()
    with pytest.raises(ValueError):
        use_case._parse_group({"chat_id": 1, "delivery": {"mode": "daily"}})


def test_validate_delivery_config_ok() -> None:
    use_case = _use_case()
    group = use_case._parse_group(
        {"chat_id": 1, "delivery": {"mode": "daily", "time": "08:00"}}
    )
    assert group.delivery.mode == "daily"
    assert group.delivery.time_local == "08:00"
