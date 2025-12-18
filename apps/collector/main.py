"""Entry point for the Telegram collector MVP."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from google.api_core import exceptions as google_exceptions

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from src.application.services.prefilter import should_run_llm
from src.application.use_cases.filter_message_with_gemini import (
    FilterMessageWithGeminiUseCase,
)
from src.application.use_cases.log_telegram_message import LogTelegramMessageUseCase
from src.application.use_cases.store_message_and_decision import (
    StoreMessageAndDecisionUseCase,
)
from src.application.use_cases.sync_categories_and_groups_from_config import (
    SyncCategoriesAndGroupsFromConfigUseCase,
)
from src.domain.entities import DecisionRecord, MessageRecord
from src.infrastructure.db.engine import get_session_factory
from src.infrastructure.db.repositories import (
    SQLAlchemyCategoryRepository,
    SQLAlchemyMessageDecisionRepository,
)
from src.infrastructure.llm_gemini import GeminiFilterClient
from src.infrastructure.telegram_client.collector_client import TelegramCollectorClient

DEFAULT_SESSION_NAME = "pulsedidgest"
DOTENV_PATH = PROJECT_ROOT / ".env"
CATEGORIES_CONFIG = PROJECT_ROOT / "config" / "categories.yml"


@dataclass
class CollectorSettings:
    api_id: int
    api_hash: str
    source_chat: str
    session_name: str
    gemini_api_key: str
    gemini_model: str | None
    gemini_cooldown_seconds: int


class GeminiCooldownManager:
    """Controls cooldown periods after hitting Gemini rate limits."""

    def __init__(self, cooldown_seconds: int) -> None:
        self._cooldown_seconds = max(0, cooldown_seconds)
        self._cooldown_until: datetime | None = None

    def activate(self) -> None:
        if self._cooldown_seconds <= 0:
            return
        self._cooldown_until = datetime.utcnow() + timedelta(
            seconds=self._cooldown_seconds
        )

    def in_cooldown(self) -> bool:
        if not self._cooldown_until:
            return False
        if datetime.utcnow() >= self._cooldown_until:
            self._cooldown_until = None
            return False
        return True

    def remaining_seconds(self) -> int:
        if not self._cooldown_until:
            return 0
        remaining = (self._cooldown_until - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))


def load_settings() -> CollectorSettings:
    api_id = _require_env("TELEGRAM_API_ID")
    api_hash = _require_env("TELEGRAM_API_HASH")
    source_chat = _require_env("TELEGRAM_SOURCE_CHAT")
    session_name = os.getenv("TELETHON_SESSION_NAME", DEFAULT_SESSION_NAME)
    gemini_api_key = _require_env("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL") or None
    cooldown_raw = os.getenv("GEMINI_COOLDOWN_SECONDS", "60")
    _require_env("DATABASE_URL")

    try:
        api_id_int = int(api_id)
    except ValueError as exc:  # pragma: no cover - validation guard
        raise ValueError("TELEGRAM_API_ID must be an integer") from exc

    try:
        cooldown_seconds = max(0, int(cooldown_raw))
    except ValueError as exc:  # pragma: no cover
        raise ValueError("GEMINI_COOLDOWN_SECONDS must be an integer") from exc

    return CollectorSettings(
        api_id=api_id_int,
        api_hash=api_hash,
        source_chat=source_chat,
        session_name=session_name,
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
        gemini_cooldown_seconds=cooldown_seconds,
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
    message_repository = SQLAlchemyMessageDecisionRepository(session_factory=session_factory)
    store_use_case = StoreMessageAndDecisionUseCase(
        repository=message_repository,
        logger=logger,
    )
    category_repository = SQLAlchemyCategoryRepository(session_factory=session_factory)
    sync_use_case = SyncCategoriesAndGroupsFromConfigUseCase(
        repository=category_repository,
        config_path=CATEGORIES_CONFIG,
        logger=logger,
    )
    category_registry = sync_use_case.execute()
    cooldown = GeminiCooldownManager(settings.gemini_cooldown_seconds)

    async def handle_event(event):
        await log_use_case.handle(event)
        message = getattr(event, "message", None)
        if message is None:
            logger.warning("Received event without message payload: %s", event)
            return

        chat_id_raw = getattr(event, "chat_id", None)
        message_id_raw = getattr(message, "id", None)
        if chat_id_raw is None or message_id_raw is None:
            logger.warning(
                "Skipping message without chat_id/id (chat=%s, message=%s)",
                chat_id_raw,
                message_id_raw,
            )
            return

        try:
            chat_id = int(chat_id_raw)
            source_message_id = int(message_id_raw)
        except (TypeError, ValueError):
            logger.warning(
                "Skipping message with non-integer identifiers (chat=%s, message=%s)",
                chat_id_raw,
                message_id_raw,
            )
            return

        message_text = getattr(message, "message", "") or ""
        text_stripped = message_text.strip()
        if not text_stripped:
            logger.info(
                "Skipping empty text message chat=%s message_id=%s",
                chat_id,
                source_message_id,
            )
            return

        categories = category_registry.get_categories_for_chat(chat_id)
        if not categories:
            logger.debug("No categories configured for chat %s", chat_id)
            return

        message_record = MessageRecord(
            source_chat_id=chat_id,
            source_message_id=source_message_id,
            date=getattr(message, "date", None) or datetime.utcnow(),
            text=message_text,
        )
        await store_use_case.ensure_message(message_record)

        for category in categories:
            if not category.is_enabled:
                continue
            should_run, reason = should_run_llm(message_text, category.prefilter)
            if not should_run:
                logger.info(
                    "Prefilter skipped category=%s reason=%s",
                    category.name,
                    reason,
                )
                continue

            if cooldown.in_cooldown():
                logger.warning(
                    "Cooldown active (%ss remaining); skipping LLM for category=%s",
                    cooldown.remaining_seconds(),
                    category.name,
                )
                continue

            try:
                decision = await filter_use_case.classify(
                    message_text=message_text,
                    category_name=category.name,
                    category_prompt=category.prompt,
                )
            except google_exceptions.ResourceExhausted as exc:
                logger.warning(
                    "Gemini quota exhausted for category=%s: %s",
                    category.name,
                    exc,
                )
                cooldown.activate()
                await store_use_case.record_error(
                    message_record,
                    category.id,
                    "RESOURCE_EXHAUSTED",
                    str(exc),
                )
                continue
            except Exception as exc:  # pragma: no cover - runtime guard
                logger.error(
                    "Gemini classification failed for category=%s: %s",
                    category.name,
                    exc,
                )
                await store_use_case.record_error(
                    message_record,
                    category.id,
                    exc.__class__.__name__,
                    str(exc),
                )
                continue

            decision_record = DecisionRecord(
                category_id=category.id,
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
