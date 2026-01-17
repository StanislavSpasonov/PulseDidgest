"""Environment-driven settings loaders."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

DEFAULT_SESSION_NAME = "pulsedidgest"


@dataclass(frozen=True)
class CollectorSettings:
    api_id: int
    api_hash: str
    session_name: str
    gemini_api_key: str
    gemini_model: str | None
    gemini_cooldown_seconds: int
    bot_token: str | None
    admin_user_id: int | None
    default_tz: str
    config_sync_mode: str
    delivery_tick_seconds: int
    refresh_seconds: int
    source_chat_override: str | None


@dataclass(frozen=True)
class BotSettings:
    token: str
    admin_user_id: int
    default_tz: str
    telethon_api_id: int
    telethon_api_hash: str
    session_name: str
    telethon_dialog_limit: int
    gemini_model: str
    gemini_cooldown_seconds: int
    config_sync_mode: str
    delivery_tick_seconds: int


def load_env_file(dotenv_path: Path) -> None:
    load_dotenv(dotenv_path=dotenv_path)


def load_collector_settings() -> CollectorSettings:
    api_id = _require_env("TELEGRAM_API_ID")
    api_hash = _require_env("TELEGRAM_API_HASH")
    source_chat = os.getenv("TELEGRAM_SOURCE_CHAT")
    collector_override = os.getenv("COLLECTOR_TELETHON_SESSION_NAME")
    session_env = os.getenv("TELETHON_SESSION") or os.getenv("TELETHON_SESSION_PATH")
    session_name = os.getenv("TELETHON_SESSION_NAME", DEFAULT_SESSION_NAME)
    session_name = resolve_telethon_session_path(
        collector_override or session_env,
        session_name,
    )
    gemini_api_key = _require_env("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL") or None
    cooldown_seconds = _get_int_env("GEMINI_COOLDOWN_SECONDS", 60, min_value=0)
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    admin_user_id = _get_optional_int_env("TELEGRAM_ADMIN_USER_ID")
    if admin_user_id is None:
        admin_user_id = _get_optional_int_env("ADMIN_TELEGRAM_ID")
    default_tz = os.getenv("DEFAULT_TZ", "Europe/Berlin")
    config_mode = os.getenv("CONFIG_SYNC_MODE", "seed_if_empty")
    delivery_tick_seconds = _get_int_env("DELIVERY_TICK_SECONDS", 60, min_value=15)
    refresh_seconds = _get_int_env("COLLECTOR_REFRESH_SECONDS", 30, min_value=5)
    _require_env("DATABASE_URL")

    return CollectorSettings(
        api_id=_parse_int(api_id, "TELEGRAM_API_ID"),
        api_hash=api_hash,
        session_name=session_name,
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
        gemini_cooldown_seconds=cooldown_seconds,
        bot_token=bot_token,
        admin_user_id=admin_user_id,
        default_tz=default_tz,
        config_sync_mode=config_mode,
        delivery_tick_seconds=delivery_tick_seconds,
        refresh_seconds=refresh_seconds,
        source_chat_override=source_chat,
    )


def load_bot_settings() -> BotSettings:
    token = _require_env("TELEGRAM_BOT_TOKEN")
    admin_user_id = _get_optional_int_env("TELEGRAM_ADMIN_USER_ID")
    if admin_user_id is None:
        admin_user_id = _get_optional_int_env("ADMIN_TELEGRAM_ID")
    admin_user_id = admin_user_id or 0
    default_tz = os.getenv("DEFAULT_TZ", "Europe/Berlin")
    telethon_api_id = _get_int_env("TELEGRAM_API_ID", 0, min_value=0)
    telethon_api_hash = os.getenv("TELEGRAM_API_HASH")
    if not telethon_api_id or not telethon_api_hash:
        raise RuntimeError(
            "TELEGRAM_API_ID and TELEGRAM_API_HASH are required for Telethon-based group management"
        )
    ui_override = os.getenv("UI_TELETHON_SESSION")
    session_env = os.getenv("TELETHON_SESSION") or os.getenv("TELETHON_SESSION_PATH")
    collector_override = os.getenv("COLLECTOR_TELETHON_SESSION_NAME")
    session_name = os.getenv("TELETHON_SESSION_NAME", DEFAULT_SESSION_NAME)
    session_name = resolve_telethon_session_path(
        ui_override or session_env or collector_override,
        session_name,
    )
    telethon_dialog_limit = _get_int_env("TELETHON_DIALOGS_LIMIT", 200, min_value=1)
    gemini_model = os.getenv("GEMINI_MODEL", "models/gemini-flash-latest")
    gemini_cooldown_seconds = _get_int_env("GEMINI_COOLDOWN_SECONDS", 60, min_value=0)
    config_sync_mode = os.getenv("CONFIG_SYNC_MODE", "seed_if_empty")
    delivery_tick_seconds = _get_int_env("DELIVERY_TICK_SECONDS", 60, min_value=15)

    return BotSettings(
        token=token,
        admin_user_id=admin_user_id,
        default_tz=default_tz,
        telethon_api_id=telethon_api_id,
        telethon_api_hash=telethon_api_hash,
        session_name=session_name,
        telethon_dialog_limit=telethon_dialog_limit,
        gemini_model=gemini_model,
        gemini_cooldown_seconds=gemini_cooldown_seconds,
        config_sync_mode=config_sync_mode,
        delivery_tick_seconds=delivery_tick_seconds,
    )


def _require_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise RuntimeError(f"Environment variable {var_name} is required")
    return value


def _parse_int(value: str, name: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _get_int_env(var_name: str, default: int, min_value: int | None = None) -> int:
    raw = os.getenv(var_name)
    if raw is None or raw == "":
        return default
    value = _parse_int(raw, var_name)
    if min_value is not None:
        return max(min_value, value)
    return value


def resolve_telethon_session_path(
    session_value: str | None,
    session_name: str | None,
    default_name: str = DEFAULT_SESSION_NAME,
) -> str:
    name = (session_name or "").strip() or default_name
    if not session_value or not session_value.strip():
        return name
    raw = session_value.strip()
    path = Path(raw)
    if _looks_like_session_dir(path, raw, name):
        return str(path / name)
    return str(path)


def _looks_like_session_dir(path: Path, raw: str, session_name: str) -> bool:
    if raw.endswith(("/", "\\")):
        return True
    if path.exists() and path.is_dir():
        return True
    if session_name and path.name.startswith(".") and path.suffix == "":
        return True
    return False


def log_telethon_session_diagnostics(
    logger,
    session_path: str,
    label: str,
) -> None:
    path = Path(session_path)
    exists = path.exists()
    if exists and path.is_file():
        size: Optional[int] = path.stat().st_size
        kind = "file"
    elif exists and path.is_dir():
        size = None
        kind = "dir"
    else:
        size = None
        kind = "missing"
    logger.info(
        "Telethon session [%s] path=%s exists=%s type=%s size=%s",
        label,
        session_path,
        exists,
        kind,
        size if size is not None else "-",
    )


def _get_optional_int_env(var_name: str) -> int | None:
    raw = os.getenv(var_name)
    if raw is None or raw == "":
        return None
    return _parse_int(raw, var_name)
