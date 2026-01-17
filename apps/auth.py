"""Telethon authorization helper."""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from telethon import TelegramClient, errors

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
            await _authorize_with_retries(client, logger)
        if await client.is_user_authorized():
            logger.info("Telethon authorized OK for session=%s", settings.session_name)
        else:
            logger.error("Telethon authorization failed for session=%s", settings.session_name)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())


async def _authorize_with_retries(client: TelegramClient, logger: logging.Logger) -> None:
    while True:
        phone = await asyncio.to_thread(input, "Please enter your phone (e.g. +491234567890): ")
        phone = (phone or "").strip()
        if not phone:
            logger.warning("Phone number is required.")
            continue
        try:
            await client.send_code_request(phone)
        except errors.PhoneNumberInvalidError:
            logger.warning("Invalid phone number. Please try again.")
            continue
        except errors.PhoneNumberBannedError:
            logger.error("Phone number is banned. Aborting.")
            return
        break
    while True:
        code = await asyncio.to_thread(input, "Enter the code you received: ")
        code = (code or "").strip()
        if not code:
            logger.warning("Code is required.")
            continue
        try:
            await client.sign_in(phone=phone, code=code)
            return
        except errors.PhoneCodeInvalidError:
            logger.warning("Invalid code. Please try again.")
        except errors.PhoneCodeExpiredError:
            logger.warning("Code expired. Requesting a new one.")
            await client.send_code_request(phone)
        except errors.SessionPasswordNeededError:
            password = await asyncio.to_thread(input, "Two-step password: ")
            password = (password or "").strip()
            if not password:
                logger.warning("Password is required.")
                continue
            await client.sign_in(password=password)
            return
