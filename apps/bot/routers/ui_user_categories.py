from __future__ import annotations

import asyncio

from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apps.bot.ui.callbacks import MyCategoryCb, NavCb
from apps.bot.ui.common import UiDeps, fetch_user, is_active, respond, truncate
from apps.bot.ui.list_keyboard import build_one_column_list


def _build_categories_list(categories, page: int):
    page_obj, kb = build_one_column_list(
        categories,
        label_fn=lambda category: category.name,
        callback_fn=lambda category: MyCategoryCb(action="open", category_id=str(category.id)).pack(),
        page=page,
        page_size=6,
        page_callback_fn=lambda p: MyCategoryCb(action="page", page=p).pack(),
        back_cb=NavCb(action="home").pack(),
        home_cb=NavCb(action="home").pack(),
    )
    return page_obj, kb


def _build_category_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data=MyCategoryCb(action="menu").pack())
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(1)
    return builder.as_markup()


def build_router(deps: UiDeps) -> Router:
    router = Router()

    @router.callback_query(MyCategoryCb.filter(F.action == "menu"))
    async def handle_menu(callback: types.CallbackQuery) -> None:
        user = await fetch_user(deps, callback.from_user.id)
        if not is_active(user):
            await respond(callback, "Доступ недоступен.")
            return
        categories = await asyncio.to_thread(deps.access_repo.list_categories_for_user, user.id)
        if not categories:
            await respond(callback, "Нет доступных категорий.")
            return
        _, kb = _build_categories_list(categories, 0)
        await respond(callback, "Мои категории:", kb)

    @router.callback_query(MyCategoryCb.filter(F.action == "page"))
    async def handle_page(callback: types.CallbackQuery, callback_data: MyCategoryCb) -> None:
        user = await fetch_user(deps, callback.from_user.id)
        if not is_active(user):
            await respond(callback, "Доступ недоступен.")
            return
        categories = await asyncio.to_thread(deps.access_repo.list_categories_for_user, user.id)
        if not categories:
            await respond(callback, "Нет доступных категорий.")
            return
        _, kb = _build_categories_list(categories, callback_data.page)
        await respond(callback, "Мои категории:", kb)

    @router.callback_query(MyCategoryCb.filter(F.action == "open"))
    async def handle_open(callback: types.CallbackQuery, callback_data: MyCategoryCb) -> None:
        user = await fetch_user(deps, callback.from_user.id)
        if not is_active(user):
            await respond(callback, "Доступ недоступен.")
            return
        category = await asyncio.to_thread(deps.admin_repo.get_category_by_id, callback_data.category_id)
        prompt_preview = truncate(category.prompt or "", 240)
        text = f"Категория: {category.name}\nПромпт: {prompt_preview or '<empty>'}"
        await respond(callback, text, _build_category_kb())

    return router
