"""Telethon authorization helper."""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from telethon import TelegramClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.infrastructure.config import load_env_file
from src.infrastructure.config.settings import load_telethon_auth_settings
from src.infrastructure.telegram.session_resolver import log_telethon_session_diagnostics

DOTENV_PATH = PROJECT_ROOT / ".env"


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    load_env_file(DOTENV_PATH)
    settings = load_telethon_auth_settings()
    logger = logging.getLogger("telethon.auth")
    log_telethon_session_diagnostics(logger, settings.session_name, "auth")
    client = TelegramClient(settings.session_name, settings.api_id, settings.api_hash)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            await client.start()
        if await client.is_user_authorized():
            logger.info("Telethon authorized OK for session=%s", settings.session_name)
        else:
            logger.error("Telethon authorization failed for session=%s", settings.session_name)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
