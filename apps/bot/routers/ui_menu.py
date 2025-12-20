from __future__ import annotations

import asyncio
from typing import Tuple

from aiogram import Router, types
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apps.bot.ui.callbacks import NavCb, CategoryCb, DeliveryCb, GroupCb, LinkCb, ReportCb, SettingsCb
from apps.bot.ui.common import UiDeps, is_admin, respond


def build_main_menu(admin_only: bool = True) -> Tuple[str, types.InlineKeyboardMarkup | None]:
    if not admin_only:
        return ("Меню доступно только администраторам.", None)

    builder = InlineKeyboardBuilder()
    builder.button(text="📁 Категории", callback_data=CategoryCb(action="menu").pack())
    builder.button(text="💬 Группы", callback_data=GroupCb(action="menu").pack())
    builder.button(text="🔗 Источники категорий", callback_data=LinkCb(action="menu").pack())
    builder.button(text="🚚 Доставка", callback_data=DeliveryCb(action="menu").pack())
    builder.button(text="🧪 Отладка/Отчёты", callback_data=ReportCb(action="menu").pack())
    builder.button(text="⚙️ Настройки", callback_data=SettingsCb(action="menu").pack())
    builder.adjust(1)
    text = "PulseDidgest — главное меню"
    return text, builder.as_markup()


def build_router(deps: UiDeps) -> Router:
    router = Router()

    @router.message(CommandStart())
    async def handle_start(message: types.Message) -> None:
        if not message.from_user:
            await message.answer("Cannot register without user info")
            return
        await asyncio.to_thread(
            deps.user_repo.register_user,
            message.from_user.id,
            message.chat.id,
            message.from_user.username,
        )
        menu_text, menu_kb = build_main_menu(
            admin_only=is_admin(message.from_user.id, deps.admin_user_id)
        )
        await message.answer(menu_text, reply_markup=menu_kb)

    @router.message(Command("menu"))
    async def handle_menu(message: types.Message) -> None:
        if not message.from_user or not is_admin(message.from_user.id, deps.admin_user_id):
            await message.answer("Меню доступно только администраторам.")
            return
        menu_text, menu_kb = build_main_menu(admin_only=True)
        await message.answer(menu_text, reply_markup=menu_kb)

    @router.callback_query(NavCb.filter())
    async def handle_nav(callback: types.CallbackQuery, callback_data: NavCb) -> None:
        if callback_data.action != "home":
            await callback.answer()
            return
        menu_text, menu_kb = build_main_menu(
            admin_only=is_admin(callback.from_user.id, deps.admin_user_id)
        )
        await respond(callback, menu_text, menu_kb)

    return router
