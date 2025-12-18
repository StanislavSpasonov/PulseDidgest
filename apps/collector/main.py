"""Entry point for the Telegram collector MVP."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from src.application.use_cases.filter_message_with_gemini import (
    FilterMessageWithGeminiUseCase,
)
from src.application.use_cases.log_telegram_message import LogTelegramMessageUseCase
from src.infrastructure.llm_gemini import GeminiFilterClient
from src.infrastructure.telegram_client.collector_client import TelegramCollectorClient

DEFAULT_SESSION_NAME = "pulsedidgest"
DOTENV_PATH = PROJECT_ROOT / ".env"


@dataclass
class CollectorSettings:
    api_id: int
    api_hash: str
    source_chat: str
    session_name: str
    gemini_api_key: str
    gemini_model: str | None


def load_settings() -> CollectorSettings:
    api_id = _require_env("TELEGRAM_API_ID")
    api_hash = _require_env("TELEGRAM_API_HASH")
    source_chat = _require_env("TELEGRAM_SOURCE_CHAT")
    session_name = os.getenv("TELETHON_SESSION_NAME", DEFAULT_SESSION_NAME)
    gemini_api_key = _require_env("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL") or None

    try:
        api_id_int = int(api_id)
    except ValueError as exc:  # pragma: no cover - validation guard
        raise ValueError("TELEGRAM_API_ID must be an integer") from exc

    return CollectorSettings(
        api_id=api_id_int,
        api_hash=api_hash,
        source_chat=source_chat,
        session_name=session_name,
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
    )


def load_env_file() -> None:
    load_dotenv(dotenv_path=DOTENV_PATH)


def _require_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise RuntimeError(f"Environment variable {var_name} is required")
    return value


async def run_collector(settings: CollectorSettings) -> None:
    logger = logging.getLogger("collector")
    client = TelegramCollectorClient(
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        session_name=settings.session_name,
        logger=logger,
    )
    log_use_case = LogTelegramMessageUseCase(logger=logger)
    gemini_client = GeminiFilterClient(
        api_key=settings.gemini_api_key,
        model_name=settings.gemini_model,
        logger=logger,
    )
    filter_use_case = FilterMessageWithGeminiUseCase(
        gemini_client=gemini_client,
        logger=logger,
    )

    async def handle_event(event):
        await log_use_case.handle(event)
        await filter_use_case.handle(event)

    await client.run(settings.source_chat, handle_event)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    load_env_file()
    settings = load_settings()
    try:
        asyncio.run(run_collector(settings))
    except KeyboardInterrupt:  # pragma: no cover - graceful exit
        logging.getLogger("collector").info("Collector stopped by user")


if __name__ == "__main__":
    main()
