"""Telegram bot for admin management of categories, groups, and delivery."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.infrastructure.db.engine import get_session_factory
from src.infrastructure.db.repositories import (
    SQLAlchemyUserRepository,
    SQLAlchemyAdminRepository,
    SQLAlchemyCategoryRepository,
)

DOTENV_PATH = PROJECT_ROOT / ".env"


class PromptStates(StatesGroup):
    waiting_for_prompt = State()


class GroupAddStates(StatesGroup):
    waiting_for_forward = State()


def ensure_admin(message: Message, admin_id: int) -> bool:
    if not message.from_user:
        return False
    return admin_id and message.from_user.id == admin_id


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    load_dotenv(dotenv_path=DOTENV_PATH)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required for the bot")
    admin_user_id = int(os.getenv("TELEGRAM_ADMIN_USER_ID", "0"))
    default_tz = os.getenv("DEFAULT_TZ", "Europe/Berlin")

    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())
    session_factory = get_session_factory()
    user_repo = SQLAlchemyUserRepository(session_factory=session_factory)
    admin_repo = SQLAlchemyAdminRepository(session_factory=session_factory)
    category_repo = SQLAlchemyCategoryRepository(session_factory=session_factory)

    async def send_help(message: Message) -> None:
        help_text = (
            "Commands:\n"
            "/start — register user\n"
            "/help — show this message\n"
        )
        if ensure_admin(message, admin_user_id):
            help_text += (
                "\nAdmin commands:\n"
                "/categories, /category_show <name>, /category_create <name>\n"
                "/category_prompt <name>, /category_debug_on|off <name>\n"
                "/groups, /group_add\n"
                "/bind <category> <chat_id>, /unbind <category> <chat_id>\n"
                "/delivery_show <category>, /delivery_set <category> <chat_id> <mode> [args]\n"
                "/delivery_enable|disable <category> <chat_id>\n"
                "/report <category> [hours] [limit]\n"
                "/report_group <category> <chat_id> [hours] [limit]\n"
                "/last_pass <category> [limit], /last_fail <category> [limit]\n"
                "/llm_errors [hours] [limit]"
            )
        await message.answer(help_text)

    @dp.message(CommandStart())
    async def handle_start(message: Message) -> None:
        if not message.from_user:
            await message.answer("Cannot register without user info")
            return
        await asyncio.to_thread(
            user_repo.register_user,
            message.from_user.id,
            message.chat.id,
            message.from_user.username,
        )
        await message.answer("Registered. chat_id={}".format(message.chat.id))

    @dp.message(Command("help"))
    async def handle_help(message: Message) -> None:
        await send_help(message)

    @dp.message(Command("categories"))
    async def handle_categories(message: Message) -> None:
        if not ensure_admin(message, admin_user_id):
            await message.answer("Admin only")
            return
        categories = await asyncio.to_thread(admin_repo.list_categories)
        if not categories:
            await message.answer("No categories yet")
            return
        lines = ["Categories:"]
        for cat in categories:
            lines.append(
                f"- {cat.name} (debug={'on' if cat.debug_enabled else 'off'})"
            )
        await message.answer("\n".join(lines))

    @dp.message(Command("category_create"))
    async def handle_category_create(message: Message) -> None:
        if not ensure_admin(message, admin_user_id):
            await message.answer("Admin only")
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("Usage: /category_create <name>")
            return
        name = parts[1].strip()
        try:
            await asyncio.to_thread(admin_repo.create_category, name)
            await message.answer(f"Category '{name}' created")
        except Exception as exc:
            await message.answer(f"Failed to create category: {exc}")

    @dp.message(Command("category_show"))
    async def handle_category_show(message: Message) -> None:
        if not ensure_admin(message, admin_user_id):
            await message.answer("Admin only")
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("Usage: /category_show <name>")
            return
        name = parts[1].strip()
        try:
            category, links = await asyncio.to_thread(
                admin_repo.get_category_details, name
            )
        except Exception as exc:
            await message.answer(f"Error: {exc}")
            return
        prompt_preview = (category.prompt or "").strip()
        if len(prompt_preview) > 200:
            prompt_preview = prompt_preview[:200] + "…"
        lines = [
            f"Category: {category.name}",
            f"Debug: {'on' if category.debug_enabled else 'off'}",
            f"Prompt: {prompt_preview or '<empty>'}",
            "Bindings:",
        ]
        if not links:
            lines.append("  (none)")
        else:
            for link, group in links:
                lines.append(
                    f"- chat {group.tg_chat_id} ({group.title or 'no title'}), "
                    f"mode={link.delivery_mode}, enabled={link.is_enabled}"
                )
        await message.answer("\n".join(lines))

    @dp.message(Command("category_prompt"))
    async def handle_category_prompt(message: Message, state: FSMContext) -> None:
        if not ensure_admin(message, admin_user_id):
            await message.answer("Admin only")
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("Usage: /category_prompt <name>")
            return
        name = parts[1].strip()
        await state.set_state(PromptStates.waiting_for_prompt)
        await state.update_data(category=name)
        await message.answer("Send new prompt text for category '{}'.".format(name))

    @dp.message(PromptStates.waiting_for_prompt)
    async def handle_prompt_message(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        name = data.get("category")
        if not name:
            await message.answer("No category in context. Send /category_prompt again.")
            await state.clear()
            return
        prompt = message.text or ""
        try:
            await asyncio.to_thread(admin_repo.set_category_prompt, name, prompt)
            await message.answer(f"Prompt updated for {name}")
        except Exception as exc:
            await message.answer(f"Failed to update prompt: {exc}")
        await state.clear()

    @dp.message(Command("category_debug_on"))
    async def handle_debug_on(message: Message) -> None:
        await _toggle_debug(message, True)

    @dp.message(Command("category_debug_off"))
    async def handle_debug_off(message: Message) -> None:
        await _toggle_debug(message, False)

    async def _toggle_debug(message: Message, enabled: bool) -> None:
        if not ensure_admin(message, admin_user_id):
            await message.answer("Admin only")
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer(
                "Usage: /category_debug_{} <name>".format("on" if enabled else "off")
            )
            return
        name = parts[1].strip()
        try:
            await asyncio.to_thread(admin_repo.set_category_debug, name, enabled)
            await message.answer(
                f"Debug {'enabled' if enabled else 'disabled'} for {name}"
            )
        except Exception as exc:
            await message.answer(f"Failed: {exc}")

    @dp.message(Command("groups"))
    async def handle_groups(message: Message) -> None:
        if not ensure_admin(message, admin_user_id):
            await message.answer("Admin only")
            return
        groups = await asyncio.to_thread(admin_repo.list_groups)
        if not groups:
            await message.answer("No groups registered")
            return
        lines = ["Groups:"]
        for group in groups[:30]:
            lines.append(
                f"- chat_id={group.tg_chat_id} title={group.title or '<none>'}"
            )
        await message.answer("\n".join(lines))

    @dp.message(Command("group_add"))
    async def handle_group_add(message: Message, state: FSMContext) -> None:
        if not ensure_admin(message, admin_user_id):
            await message.answer("Admin only")
            return
        await state.set_state(GroupAddStates.waiting_for_forward)
        await message.answer(
            "Forward a message from the target chat/channel to register it."
        )

    @dp.message(GroupAddStates.waiting_for_forward)
    async def handle_forwarded_group(message: Message, state: FSMContext) -> None:
        if not message.forward_from_chat:
            await message.answer("Please forward a message from the target group.")
            return
        chat = message.forward_from_chat
        await asyncio.to_thread(
            admin_repo.register_group,
            chat.id,
            chat.title or chat.full_name,
        )
        await message.answer(f"Group registered: {chat.id}")
        await state.clear()

    @dp.message(Command("bind"))
    async def handle_bind(message: Message) -> None:
        await _bind_unbind(message, bind=True)

    @dp.message(Command("unbind"))
    async def handle_unbind(message: Message) -> None:
        await _bind_unbind(message, bind=False)

    async def _bind_unbind(message: Message, bind: bool) -> None:
        if not ensure_admin(message, admin_user_id):
            await message.answer("Admin only")
            return
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer("Usage: /{} <category> <chat_id>".format(
                "bind" if bind else "unbind"
            ))
            return
        name = parts[1]
        try:
            chat_id = int(parts[2])
        except ValueError:
            await message.answer("chat_id must be integer")
            return
        try:
            if bind:
                await asyncio.to_thread(admin_repo.bind_category, name, chat_id)
                await message.answer("Binding added")
            else:
                await asyncio.to_thread(admin_repo.unbind_category, name, chat_id)
                await message.answer("Binding removed")
        except Exception as exc:
            await message.answer(f"Error: {exc}")

    @dp.message(Command("delivery_show"))
    async def handle_delivery_show(message: Message) -> None:
        if not ensure_admin(message, admin_user_id):
            await message.answer("Admin only")
            return
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("Usage: /delivery_show <category>")
            return
        name = parts[1].strip()
        try:
            rows = await asyncio.to_thread(admin_repo.get_delivery_info, name)
        except Exception as exc:
            await message.answer(f"Error: {exc}")
            return
        if not rows:
            await message.answer("No bindings for category")
            return
        lines = [f"Delivery for {name}:"]
        for link, group in rows:
            lines.append(
                f"- chat {group.tg_chat_id} ({group.title or ''}) mode={link.delivery_mode}"
                f" enabled={link.is_enabled} interval={link.delivery_interval_minutes}"
                f" time={link.delivery_time_local} tz={link.delivery_tz}"
            )
        await message.answer("\n".join(lines))

    @dp.message(Command("delivery_set"))
    async def handle_delivery_set(message: Message) -> None:
        if not ensure_admin(message, admin_user_id):
            await message.answer("Admin only")
            return
        parts = message.text.split()
        if len(parts) < 4:
            await message.answer(
                "Usage: /delivery_set <category> <chat_id> <mode> [args] [tz]"
            )
            return
        name = parts[1]
        try:
            chat_id = int(parts[2])
        except ValueError:
            await message.answer("chat_id must be integer")
            return
        mode = parts[3].lower()
        interval = None
        time_local = None
        timezone = default_tz
        if mode == "interval":
            if len(parts) < 5:
                await message.answer("Interval mode requires minutes")
                return
            try:
                interval = int(parts[4])
            except ValueError:
                await message.answer("Minutes must be integer")
                return
            if len(parts) >= 6:
                timezone = parts[5]
        elif mode == "daily":
            if len(parts) < 5:
                await message.answer("Daily mode requires HH:MM")
                return
            time_local = parts[4]
            if len(parts) >= 6:
                timezone = parts[5]
        elif mode not in {"instant", "hourly"}:
            await message.answer("Mode must be instant/hourly/interval/daily")
            return
        try:
            await asyncio.to_thread(
                admin_repo.set_delivery,
                name,
                chat_id,
                mode,
                interval,
                time_local,
                timezone,
            )
            await message.answer("Delivery updated")
        except Exception as exc:
            await message.answer(f"Error: {exc}")

    @dp.message(Command("delivery_enable"))
    async def handle_delivery_enable(message: Message) -> None:
        await _set_delivery_enabled(message, True)

    @dp.message(Command("delivery_disable"))
    async def handle_delivery_disable(message: Message) -> None:
        await _set_delivery_enabled(message, False)

    async def _set_delivery_enabled(message: Message, enabled: bool) -> None:
        if not ensure_admin(message, admin_user_id):
            await message.answer("Admin only")
            return
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer(
                "Usage: /delivery_{} <category> <chat_id>".format(
                    "enable" if enabled else "disable"
                )
            )
            return
        name = parts[1]
        try:
            chat_id = int(parts[2])
        except ValueError:
            await message.answer("chat_id must be integer")
            return
        try:
            await asyncio.to_thread(
                admin_repo.set_delivery_enabled,
                name,
                chat_id,
                enabled,
            )
            await message.answer("Delivery {}".format(
                "enabled" if enabled else "disabled"
            ))
        except Exception as exc:
            await message.answer(f"Error: {exc}")

    @dp.message(Command("report"))
    async def handle_report(message: Message) -> None:
        await _handle_report(message, per_group=False)

    @dp.message(Command("report_group"))
    async def handle_report_group(message: Message) -> None:
        await _handle_report(message, per_group=True)

    async def _handle_report(message: Message, per_group: bool) -> None:
        if not ensure_admin(message, admin_user_id):
            await message.answer("Admin only")
            return
        parts = message.text.split()
        if len(parts) < (3 if per_group else 2):
            await message.answer(
                "Usage: /{} <category> {} [hours] [limit]".format(
                    "report_group" if per_group else "report",
                    "<chat_id>" if per_group else "",
                ).strip()
            )
            return
        name = parts[1]
        idx = 2
        chat_id = None
        if per_group:
            try:
                chat_id = int(parts[2])
            except ValueError:
                await message.answer("chat_id must be integer")
                return
            idx = 3
        hours = int(parts[idx]) if len(parts) > idx else 24
        limit = int(parts[idx + 1]) if len(parts) > idx + 1 else 10
        try:
            if per_group:
                pass_count, fail_count, rows = await asyncio.to_thread(
                    admin_repo.report_group, name, chat_id, hours, limit
                )
            else:
                pass_count, fail_count, rows = await asyncio.to_thread(
                    admin_repo.report_category, name, hours, limit
                )
        except Exception as exc:
            await message.answer(f"Error: {exc}")
            return
        lines = [
            f"Report for {name} ({'chat '+str(chat_id) if chat_id else 'all'})",
            f"Pass: {pass_count}  Fail: {fail_count}",
            "Recent:",
        ]
        if not rows:
            lines.append("(none)")
        else:
            for decision, message_row in rows:
                text = (message_row.text or "").strip().replace("\n", " ")
                snippet = text[:200] + ("…" if len(text) > 200 else "")
                lines.append(
                    f"- {decision.created_at:%Y-%m-%d %H:%M} score={decision.score:.2f}"
                    f" pass={decision.passed}\n  {snippet}"
                )
        await message.answer("\n".join(lines))

    @dp.message(Command("last_pass"))
    async def handle_last_pass(message: Message) -> None:
        await _handle_last_decisions(message, passed=True)

    @dp.message(Command("last_fail"))
    async def handle_last_fail(message: Message) -> None:
        await _handle_last_decisions(message, passed=False)

    async def _handle_last_decisions(message: Message, passed: Optional[bool]) -> None:
        if not ensure_admin(message, admin_user_id):
            await message.answer("Admin only")
            return
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("Usage: /last_{} <category> [limit]".format(
                "pass" if passed else "fail"
            ))
            return
        name = parts[1]
        limit = int(parts[2]) if len(parts) > 2 else 10
        try:
            rows = await asyncio.to_thread(
                admin_repo.last_decisions, name, passed, limit
            )
        except Exception as exc:
            await message.answer(f"Error: {exc}")
            return
        if not rows:
            await message.answer("No decisions found")
            return
        lines = [f"Last {'pass' if passed else 'fail'} for {name}:"]
        for decision, message_row in rows:
            snippet = (message_row.text or "").strip()[:200]
            lines.append(
                f"- {decision.created_at:%Y-%m-%d %H:%M} score={decision.score:.2f}"
                f" reason={decision.reason}\n  {snippet}"
            )
        await message.answer("\n".join(lines))

    @dp.message(Command("llm_errors"))
    async def handle_llm_errors(message: Message) -> None:
        if not ensure_admin(message, admin_user_id):
            await message.answer("Admin only")
            return
        parts = message.text.split()
        hours = int(parts[1]) if len(parts) > 1 else 24
        limit = int(parts[2]) if len(parts) > 2 else 10
        try:
            rows = await asyncio.to_thread(
                admin_repo.list_llm_errors, hours, limit
            )
        except Exception as exc:
            await message.answer(f"Error: {exc}")
            return
        if not rows:
            await message.answer("No LLM errors found")
            return
        lines = ["LLM errors:"]
        for error, category in rows:
            lines.append(
                f"- {error.created_at:%Y-%m-%d %H:%M} [{category.name}]"
                f" code={error.error_code} text={error.error_text[:120]}"
            )
        await message.answer("\n".join(lines))

    logging.info("Bot polling started")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
