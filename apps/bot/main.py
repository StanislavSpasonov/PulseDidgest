"""Telegram bot for registering users via /start."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.infrastructure.db.engine import get_session_factory
from src.infrastructure.db.repositories import SQLAlchemyUserRepository

DOTENV_PATH = PROJECT_ROOT / ".env"


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    load_dotenv(dotenv_path=DOTENV_PATH)
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required for the bot")

    bot = Bot(token=token)
    dp = Dispatcher()
    session_factory = get_session_factory()
    user_repo = SQLAlchemyUserRepository(session_factory=session_factory)

    @dp.message(CommandStart())
    async def handle_start(message: types.Message) -> None:
        if not message.from_user:
            await message.answer("Cannot register without user info")
            return
        await asyncio.to_thread(
            user_repo.register_user,
            message.from_user.id,
            message.chat.id,
            message.from_user.username,
        )
        await message.answer(f"Registered. chat_id={message.chat.id}")

    logging.info("Bot polling started")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
