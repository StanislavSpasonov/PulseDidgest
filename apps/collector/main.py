"""Entry point for the Telegram collector MVP."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from src.application.use_cases.filter_message_with_gemini import (
    FilterMessageWithGeminiUseCase,
)
from src.application.use_cases.log_telegram_message import LogTelegramMessageUseCase
from src.application.use_cases.store_message_and_decision import (
    StoreMessageAndDecisionUseCase,
)
from src.domain.entities import DecisionRecord, MessageRecord
from src.infrastructure.db.engine import get_session_factory
from src.infrastructure.db.repositories import SQLAlchemyMessageDecisionRepository
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
    _require_env("DATABASE_URL")

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
    session_factory = get_session_factory()
    repository = SQLAlchemyMessageDecisionRepository(session_factory=session_factory)
    store_use_case = StoreMessageAndDecisionUseCase(
        repository=repository,
        logger=logger,
    )

    async def handle_event(event):
        await log_use_case.handle(event)
        decision = await filter_use_case.handle(event)
        if decision is None:
            return
        await persist_decision(event, decision)

    async def persist_decision(event, decision):
        message = getattr(event, "message", None)
        if message is None:
            logger.warning("Persistence skipped: event without message %s", event)
            return

        chat_id = getattr(event, "chat_id", None)
        message_id = getattr(message, "id", None)
        message_date = getattr(message, "date", None) or datetime.utcnow()
        if chat_id is None or message_id is None:
            logger.warning(
                "Persistence skipped: missing chat_id/message_id (chat=%s, message=%s)",
                chat_id,
                message_id,
            )
            return

        message_record = MessageRecord(
            source_chat_id=int(chat_id),
            source_message_id=int(message_id),
            date=message_date,
            text=getattr(message, "message", None),
        )
        decision_record = DecisionRecord(
            model=decision.model,
            prompt_name=decision.prompt_name,
            prompt_version=decision.prompt_version,
            passed=decision.passed,
            score=decision.score,
            reason=decision.reason,
        )
        await store_use_case.handle(message_record, decision_record)

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
