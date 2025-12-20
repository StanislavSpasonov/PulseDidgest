"""Entry point for the Telegram collector MVP."""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from google.api_core import exceptions as google_exceptions

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.application.services.digest_engine import DigestDeliveryEngine
from src.application.services.notifier import DebugThrottle, UserNotifier
from src.application.services.prefilter import should_run_llm
from src.application.use_cases.deliver_instant import DeliverInstantUseCase
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
    SQLAlchemyDeliveryRepository,
    SQLAlchemyMessageDecisionRepository,
    SQLAlchemyUserRepository,
)
from src.infrastructure.config import load_collector_settings, load_env_file
from src.infrastructure.llm_gemini import GeminiFilterClient
from src.infrastructure.telegram_bot import TelegramBotSender
from src.infrastructure.telegram_client.collector_client import TelegramCollectorClient

DOTENV_PATH = PROJECT_ROOT / ".env"
CATEGORIES_CONFIG = PROJECT_ROOT / "config" / "categories.yml"


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




async def run_collector(settings: CollectorSettings) -> None:
    logger = logging.getLogger("collector")
    session_factory = get_session_factory()
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
    message_repository = SQLAlchemyMessageDecisionRepository(session_factory=session_factory)
    category_repository = SQLAlchemyCategoryRepository(session_factory=session_factory)
    delivery_repository = SQLAlchemyDeliveryRepository(session_factory=session_factory)
    user_repository = SQLAlchemyUserRepository(session_factory=session_factory)

    sync_use_case = SyncCategoriesAndGroupsFromConfigUseCase(
        repository=category_repository,
        config_path=CATEGORIES_CONFIG,
        config_mode=settings.config_sync_mode,
        default_tz=settings.default_tz,
        logger=logger,
    )
    category_registry = sync_use_case.execute()

    notifier: UserNotifier | None = None
    bot_sender: TelegramBotSender | None = None
    instant_delivery: DeliverInstantUseCase | None = None
    digest_engine: DigestDeliveryEngine | None = None
    debug_throttle = DebugThrottle()

    if settings.bot_token:
        bot_sender = TelegramBotSender(settings.bot_token)
        notifier = UserNotifier(
            user_repository=user_repository,
            sender=bot_sender,
            admin_chat_id=settings.admin_user_id,
            logger=logger,
        )
        instant_delivery = DeliverInstantUseCase(
            decision_repository=message_repository,
            notifier=notifier,
            logger=logger,
        )
        digest_engine = DigestDeliveryEngine(
            repository=delivery_repository,
            notifier=notifier,
            tick_seconds=settings.delivery_tick_seconds,
            logger=logger,
        )
        digest_engine.start()
    else:
        logger.info("TELEGRAM_BOT_TOKEN not configured; delivery and debug notifications disabled")

    store_use_case = StoreMessageAndDecisionUseCase(
        repository=message_repository,
        logger=logger,
    )
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
        if not message_text.strip():
            logger.info(
                "Skipping empty text message chat=%s message_id=%s",
                chat_id,
                source_message_id,
            )
            return

        bindings = category_registry.get_categories_for_chat(chat_id)
        if not bindings:
            logger.debug("No categories configured for chat %s", chat_id)
            return

        message_record = MessageRecord(
            source_chat_id=chat_id,
            source_message_id=source_message_id,
            date=getattr(message, "date", None) or datetime.utcnow(),
            text=message_text,
        )
        await store_use_case.ensure_message(message_record)

        for binding in bindings:
            if not binding.is_enabled:
                continue
            should_run, reason = should_run_llm(message_text, binding.prefilter)
            if not should_run:
                logger.info(
                    "Prefilter skipped category=%s reason=%s",
                    binding.category_name,
                    reason,
                )
                continue

            if cooldown.in_cooldown():
                logger.warning(
                    "Cooldown active (%ss remaining); skipping LLM for category=%s",
                    cooldown.remaining_seconds(),
                    binding.category_name,
                )
                continue

            try:
                decision = await filter_use_case.classify(
                    message_text=message_text,
                    category_name=binding.category_name,
                    category_prompt=binding.prompt,
                )
            except google_exceptions.ResourceExhausted as exc:
                logger.warning(
                    "Gemini quota exhausted for category=%s: %s",
                    binding.category_name,
                    exc,
                )
                cooldown.activate()
                await store_use_case.record_error(
                    message_record,
                    binding.category_id,
                    "RESOURCE_EXHAUSTED",
                    str(exc),
                )
                continue
            except Exception as exc:  # pragma: no cover
                logger.error(
                    "Gemini classification failed for category=%s: %s",
                    binding.category_name,
                    exc,
                )
                await store_use_case.record_error(
                    message_record,
                    binding.category_id,
                    exc.__class__.__name__,
                    str(exc),
                )
                continue

            decision_record = DecisionRecord(
                category_id=binding.category_id,
                model=decision.model,
                prompt_name=decision.prompt_name,
                prompt_version=decision.prompt_version,
                passed=decision.passed,
                score=decision.score,
                reason=decision.reason,
            )
            save_result = await store_use_case.handle(message_record, decision_record)
            if save_result is None:
                continue
            _, decision_db_id = save_result

            if (
                decision_record.passed
                and binding.delivery_mode == "instant"
                and binding.is_enabled
                and instant_delivery
            ):
                await instant_delivery.deliver(
                    decision_db_id,
                    decision_record,
                    binding.category_name,
                    message_text,
                    binding.group_title,
                )

            if (
                notifier
                and binding.debug_enabled
                and settings.admin_user_id
            ):
                allow, warn = debug_throttle.check(binding.category_id)
                if allow:
                    snippet = (message_text or "").strip()[:400]
                    debug_text = (
                        f"[DEBUG {binding.category_name}] pass={decision_record.passed}"
                        f" score={decision_record.score:.2f}\n"
                        f"Reason: {decision_record.reason}\n"
                        f"Chat: {binding.chat_id}\n"
                        f"{snippet}"
                    )
                    await notifier.notify_admin(debug_text)
                elif warn:
                    await notifier.notify_admin(
                        f"[DEBUG {binding.category_name}] too many events, throttling"
                    )

    try:
        await client.run(settings.source_chat, handle_event)
    finally:
        if digest_engine is not None:
            await digest_engine.stop()
        if bot_sender is not None:
            await bot_sender.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    load_env_file(DOTENV_PATH)
    settings = load_collector_settings()
    try:
        asyncio.run(run_collector(settings))
    except KeyboardInterrupt:  # pragma: no cover - graceful exit
        logging.getLogger("collector").info("Collector stopped by user")


if __name__ == "__main__":
    main()
