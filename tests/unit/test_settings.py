from __future__ import annotations

import pytest

from src.infrastructure.config import load_bot_settings, load_collector_settings


def test_load_bot_settings_parses_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_API_ID", "123")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
    monkeypatch.setenv("TELEGRAM_ADMIN_USER_ID", "42")
    monkeypatch.setenv("TELETHON_DIALOGS_LIMIT", "300")
    monkeypatch.setenv("GEMINI_MODEL", "models/test")
    monkeypatch.setenv("GEMINI_COOLDOWN_SECONDS", "10")
    monkeypatch.setenv("CONFIG_SYNC_MODE", "off")
    monkeypatch.setenv("DELIVERY_TICK_SECONDS", "20")

    settings = load_bot_settings()

    assert settings.token == "token"
    assert settings.telethon_api_id == 123
    assert settings.telethon_api_hash == "hash"
    assert settings.admin_user_id == 42
    assert settings.telethon_dialog_limit == 300
    assert settings.gemini_model == "models/test"
    assert settings.gemini_cooldown_seconds == 10
    assert settings.config_sync_mode == "off"
    assert settings.delivery_tick_seconds == 20


def test_load_collector_settings_enforces_min_delivery_tick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_API_ID", "123")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("DELIVERY_TICK_SECONDS", "1")
    monkeypatch.setenv("COLLECTOR_REFRESH_SECONDS", "10")

    settings = load_collector_settings()

    assert settings.delivery_tick_seconds == 15
    assert settings.refresh_seconds == 10
    assert settings.source_chat_override is None


def test_load_collector_settings_invalid_api_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_API_ID", "nope")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

    with pytest.raises(ValueError):
        load_collector_settings()


def test_load_bot_settings_missing_telethon_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash")

    with pytest.raises(RuntimeError):
        load_bot_settings()
