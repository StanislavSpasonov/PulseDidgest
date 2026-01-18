from __future__ import annotations

import asyncio
from typing import Tuple

from aiogram import F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apps.bot.ui.callbacks import (
    AccessCb,
    CategoryCb,
    DeliveryCb,
    FeedbackCb,
    GroupCb,
    InboxCb,
    LinkCb,
    MyCategoryCb,
    NavCb,
    ReportCb,
    SettingsCb,
    UserCb,
    UserDeliveryCb,
)
from apps.bot.ui.common import (
    UiDeps,
    fetch_user,
    is_active,
    is_admin,
    is_blocked,
    is_pending,
    is_power,
    respond,
)
from apps.bot.ui.reply_menu import build_menu_button_keyboard


def build_main_menu(
    user,
    admin_user_id: int,
) -> Tuple[str, types.InlineKeyboardMarkup | None]:
    if not user:
        return ("Сначала выполните /start.", None)

    if is_pending(user):
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Запросить доступ", callback_data=FeedbackCb(action="request_access").pack())
        builder.button(text="✉️ Обратная связь", callback_data=FeedbackCb(action="menu").pack())
        builder.adjust(1)
        return ("Доступ ожидает подтверждения.", builder.as_markup())

    if is_blocked(user):
        builder = InlineKeyboardBuilder()
        builder.button(text="✉️ Обратная связь", callback_data=FeedbackCb(action="menu").pack())
        builder.adjust(1)
        return ("Доступ ограничен. Если это ошибка, напишите админу.", builder.as_markup())

    builder = InlineKeyboardBuilder()
    if is_admin(user, admin_user_id):
        builder.button(text="👥 Пользователи", callback_data=UserCb(action="menu").pack())
        builder.button(text="📁 Категории", callback_data=CategoryCb(action="menu").pack())
        builder.button(text="🔑 Доступ к категориям", callback_data=AccessCb(action="menu").pack())
        builder.button(text="💬 Источники", callback_data=GroupCb(action="menu").pack())
        builder.button(text="🔗 Привязки", callback_data=LinkCb(action="menu").pack())
        builder.button(text="🚚 Доставка", callback_data=DeliveryCb(action="menu").pack())
        builder.button(text="📥 Inbox", callback_data=InboxCb(action="menu").pack())
        builder.button(text="🧪 Debug/Reports", callback_data=ReportCb(action="menu").pack())
        builder.button(text="⚙️ Настройки", callback_data=SettingsCb(action="menu").pack())
        builder.adjust(1)
        return ("PulseDidgest — главное меню", builder.as_markup())

    if is_power(user, admin_user_id):
        builder.button(text="📁 Категории", callback_data=CategoryCb(action="menu").pack())
        builder.button(text="💬 Источники", callback_data=GroupCb(action="menu").pack())
        builder.button(text="🔗 Привязки", callback_data=LinkCb(action="menu").pack())
        builder.button(text="🚚 Доставка", callback_data=UserDeliveryCb(action="menu").pack())
        builder.button(text="✉️ Обратная связь", callback_data=FeedbackCb(action="menu").pack())
        builder.adjust(1)
        return ("PulseDidgest — меню", builder.as_markup())

    if is_active(user):
        builder.button(text="📁 Мои категории", callback_data=MyCategoryCb(action="menu").pack())
        builder.button(text="🚚 Доставка", callback_data=UserDeliveryCb(action="menu").pack())
        builder.button(text="✉️ Обратная связь", callback_data=FeedbackCb(action="menu").pack())
        builder.adjust(1)
        return ("PulseDidgest — меню", builder.as_markup())

    return ("Доступ недоступен. Используйте /start.", None)


def build_router(deps: UiDeps) -> Router:
    router = Router()

    async def _attach_menu_keyboard(message: types.Message) -> None:
        sent = await message.answer(
            " ",
            reply_markup=build_menu_button_keyboard(),
        )
        try:
            await sent.delete()
        except Exception:
            pass

    @router.message(CommandStart())
    async def handle_start(message: types.Message, state: FSMContext) -> None:
        await state.clear()
        if not message.from_user:
            await message.answer("Cannot register without user info")
            return
        user = await asyncio.to_thread(
            deps.user_repo.upsert_user,
            message.from_user.id,
            message.chat.id,
            message.from_user.username,
            message.from_user.first_name,
            deps.admin_user_id,
        )
        menu_text, menu_kb = build_main_menu(user, deps.admin_user_id)
        await message.answer(menu_text, reply_markup=menu_kb)
        await _attach_menu_keyboard(message)

    @router.message(Command("menu"))
    async def handle_menu(message: types.Message, state: FSMContext) -> None:
        await state.clear()
        if not message.from_user:
            await message.answer("Меню недоступно.")
            return
        user = await fetch_user(deps, message.from_user.id)
        menu_text, menu_kb = build_main_menu(user, deps.admin_user_id)
        await message.answer(menu_text, reply_markup=menu_kb)
        await _attach_menu_keyboard(message)

    @router.message(Command("hide_menu"))
    async def handle_hide_menu(message: types.Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Меню скрыто.", reply_markup=ReplyKeyboardRemove())

    @router.message(F.text == "☰ Меню")
    async def handle_menu_button(message: types.Message, state: FSMContext) -> None:
        await state.clear()
        if not message.from_user:
            await message.answer("Меню недоступно.")
            return
        user = await fetch_user(deps, message.from_user.id)
        menu_text, menu_kb = build_main_menu(user, deps.admin_user_id)
        await message.answer(menu_text, reply_markup=menu_kb)
        await _attach_menu_keyboard(message)

    @router.callback_query(NavCb.filter())
    async def handle_nav(callback: types.CallbackQuery, callback_data: NavCb) -> None:
        if callback_data.action != "home":
            await callback.answer()
            return
        user = await fetch_user(deps, callback.from_user.id)
        menu_text, menu_kb = build_main_menu(user, deps.admin_user_id)
        await respond(callback, menu_text, menu_kb)

    return router
