from __future__ import annotations

import asyncio

from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apps.bot.ui.callbacks import InboxCb, NavCb
from apps.bot.ui.common import UiDeps, fetch_user, is_admin, respond, truncate
from apps.bot.ui.list_keyboard import build_one_column_list


def _build_inbox_list(messages, page: int):
    page_obj, kb = build_one_column_list(
        messages,
        label_fn=lambda msg: f"{msg.type}: {truncate(msg.text, 40)}",
        callback_fn=lambda msg: InboxCb(action="open", message_id=str(msg.id)).pack(),
        page=page,
        page_size=6,
        page_callback_fn=lambda p: InboxCb(action="page", page=p).pack(),
        back_cb=NavCb(action="home").pack(),
        home_cb=NavCb(action="home").pack(),
    )
    return page_obj, kb


def _build_message_kb(message_id: str) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Done", callback_data=InboxCb(action="done", message_id=message_id).pack())
    builder.button(text="⬅️ Назад", callback_data=InboxCb(action="menu").pack())
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(1)
    return builder.as_markup()


def build_router(deps: UiDeps) -> Router:
    router = Router()

    async def _is_admin(user_id: int | None) -> bool:
        user = await fetch_user(deps, user_id)
        return is_admin(user, deps.admin_user_id)

    @router.callback_query(InboxCb.filter(F.action == "menu"))
    async def handle_menu(callback: types.CallbackQuery) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        messages = await asyncio.to_thread(deps.feedback_repo.list_messages, "new")
        if not messages:
            await respond(callback, "Inbox пуст.")
            return
        _, kb = _build_inbox_list(messages, 0)
        await respond(callback, "Inbox (новые):", kb)

    @router.callback_query(InboxCb.filter(F.action == "page"))
    async def handle_page(callback: types.CallbackQuery, callback_data: InboxCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        messages = await asyncio.to_thread(deps.feedback_repo.list_messages, "new")
        if not messages:
            await respond(callback, "Inbox пуст.")
            return
        _, kb = _build_inbox_list(messages, callback_data.page)
        await respond(callback, "Inbox (новые):", kb)

    @router.callback_query(InboxCb.filter(F.action == "open"))
    async def handle_open(callback: types.CallbackQuery, callback_data: InboxCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        message_id = callback_data.message_id
        if not message_id:
            await respond(callback, "Сообщение не найдено.")
            return
        messages = await asyncio.to_thread(deps.feedback_repo.list_messages, None)
        msg = next((m for m in messages if m.id == message_id), None)
        if not msg:
            await respond(callback, "Сообщение не найдено.")
            return
        user = await asyncio.to_thread(deps.user_repo.get_by_id, msg.user_id)
        who = f"@{user.username}" if user and user.username else f"user_id={msg.user_id}"
        text = f"Тип: {msg.type}\nОт: {who}\n\n{msg.text}"
        await respond(callback, text, _build_message_kb(message_id))

    @router.callback_query(InboxCb.filter(F.action == "done"))
    async def handle_done(callback: types.CallbackQuery, callback_data: InboxCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        if not callback_data.message_id:
            await respond(callback, "Сообщение не найдено.")
            return
        await asyncio.to_thread(deps.feedback_repo.mark_done, callback_data.message_id)
        await respond(callback, "Отмечено как done.")

    return router
