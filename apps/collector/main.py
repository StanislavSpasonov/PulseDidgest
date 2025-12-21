"""Entry point for the Telegram collector MVP."""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.application.services.digest_engine import DigestDeliveryEngine
from src.application.services.notifier import DebugThrottle, UserNotifier
from src.application.use_cases.deliver_instant import DeliverInstantUseCase
from src.application.use_cases.filter_message_with_gemini import (
    FilterMessageWithGeminiUseCase,
)
from src.application.use_cases.log_telegram_message import LogTelegramMessageUseCase
from src.application.use_cases.process_incoming_message import (
    IncomingMessage,
    ProcessIncomingMessageUseCase,
)
from src.application.use_cases.routing_snapshot import GetActiveRoutingSnapshotUseCase
from src.application.use_cases.store_message_and_decision import (
    StoreMessageAndDecisionUseCase,
)
from src.application.use_cases.sync_categories_and_groups_from_config import (
    SyncCategoriesAndGroupsFromConfigUseCase,
)
from src.infrastructure.db.engine import get_session_factory
from src.infrastructure.db.repositories import (
    SQLAlchemyCategoryRepository,
    SQLAlchemyDeliveryRepository,
    SQLAlchemyMessageDecisionRepository,
    SQLAlchemyUserRepository,
)
from src.infrastructure.collector.routing_cache import RoutingSnapshotCache
from src.infrastructure.config import CollectorSettings, load_collector_settings, load_env_file
from src.infrastructure.llm_gemini import GeminiFilterClient
from src.infrastructure.telegram_bot import TelegramBotSender
from src.infrastructure.telegram_client.collector_service import TelethonCollectorService
from apps.bot.ui.reply_menu import build_menu_button_keyboard

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
    client = TelethonCollectorService(
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
    sync_use_case.execute()
    routing_use_case = GetActiveRoutingSnapshotUseCase(
        repository=category_repository,
        logger=logger,
    )
    routing_cache = RoutingSnapshotCache(
        use_case=routing_use_case,
        refresh_seconds=settings.refresh_seconds,
        logger=logger,
    )

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
            reply_markup_factory=build_menu_button_keyboard,
        )
        digest_engine = DigestDeliveryEngine(
            repository=delivery_repository,
            notifier=notifier,
            tick_seconds=settings.delivery_tick_seconds,
            logger=logger,
            reply_markup_factory=build_menu_button_keyboard,
        )
        digest_engine.start()
    else:
        logger.info("TELEGRAM_BOT_TOKEN not configured; delivery and debug notifications disabled")

    store_use_case = StoreMessageAndDecisionUseCase(
        repository=message_repository,
        logger=logger,
    )
    cooldown = GeminiCooldownManager(settings.gemini_cooldown_seconds)
    process_use_case = ProcessIncomingMessageUseCase(
        filter_use_case=filter_use_case,
        store_use_case=store_use_case,
        instant_delivery_use_case=instant_delivery,
        notifier=notifier,
        debug_throttle=debug_throttle,
        cooldown=cooldown,
        logger=logger,
    )

    async def handle_event(event: IncomingMessage) -> None:
        await log_use_case.handle(event)
        snapshot = routing_cache.get_snapshot()
        await process_use_case.handle(event, snapshot)

    try:
        await routing_cache.start()
        if settings.source_chat_override:
            logger.info(
                "Collector running in single-chat override mode: %s",
                settings.source_chat_override,
            )
        await client.run(handle_event, chat_filter=settings.source_chat_override)
    finally:
        await routing_cache.stop()
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
