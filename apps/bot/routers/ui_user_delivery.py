from __future__ import annotations

import asyncio

from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apps.bot.ui.callbacks import NavCb, UserDeliveryCb
from apps.bot.ui.common import UiDeps, fetch_user, is_active, respond
from apps.bot.ui.list_keyboard import build_one_column_list


def _build_categories_list(categories, page: int):
    page_obj, kb = build_one_column_list(
        categories,
        label_fn=lambda category: category.name,
        callback_fn=lambda category: UserDeliveryCb(action="open", category_id=str(category.id)).pack(),
        page=page,
        page_size=6,
        page_callback_fn=lambda p: UserDeliveryCb(action="page", page=p).pack(),
        back_cb=NavCb(action="home").pack(),
        home_cb=NavCb(action="home").pack(),
    )
    return page_obj, kb


def _build_delivery_kb(category_id: str, enabled: bool) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    toggle_text = "✅ Вкл" if not enabled else "⛔ Выкл"
    builder.button(text=toggle_text, callback_data=UserDeliveryCb(action="toggle", category_id=category_id).pack())
    builder.button(text="⚡ Instant", callback_data=UserDeliveryCb(action="instant", category_id=category_id).pack())
    builder.button(text="⏱️ Digest 60m", callback_data=UserDeliveryCb(action="interval_60", category_id=category_id).pack())
    builder.button(text="🕘 Digest daily 09:00", callback_data=UserDeliveryCb(action="daily_0900", category_id=category_id).pack())
    builder.button(text="⬅️ Назад", callback_data=UserDeliveryCb(action="menu").pack())
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(1)
    return builder.as_markup()


def build_router(deps: UiDeps) -> Router:
    router = Router()

    async def _get_user_and_categories(user_id: int | None):
        user = await fetch_user(deps, user_id)
        if not is_active(user):
            return None, []
        categories = await asyncio.to_thread(deps.access_repo.list_categories_for_user, user.id)
        return user, categories

    @router.callback_query(UserDeliveryCb.filter(F.action == "menu"))
    async def handle_menu(callback: types.CallbackQuery) -> None:
        user, categories = await _get_user_and_categories(callback.from_user.id)
        if not user:
            await respond(callback, "Доступ недоступен.")
            return
        if not categories:
            await respond(callback, "Нет доступных категорий.")
            return
        _, kb = _build_categories_list(categories, 0)
        await respond(callback, "Настройки доставки:", kb)

    @router.callback_query(UserDeliveryCb.filter(F.action == "page"))
    async def handle_page(callback: types.CallbackQuery, callback_data: UserDeliveryCb) -> None:
        user, categories = await _get_user_and_categories(callback.from_user.id)
        if not user:
            await respond(callback, "Доступ недоступен.")
            return
        if not categories:
            await respond(callback, "Нет доступных категорий.")
            return
        _, kb = _build_categories_list(categories, callback_data.page)
        await respond(callback, "Настройки доставки:", kb)

    @router.callback_query(UserDeliveryCb.filter(F.action == "open"))
    async def handle_open(callback: types.CallbackQuery, callback_data: UserDeliveryCb) -> None:
        user = await fetch_user(deps, callback.from_user.id)
        if not is_active(user):
            await respond(callback, "Доступ недоступен.")
            return
        category = await asyncio.to_thread(deps.admin_repo.get_category_by_id, callback_data.category_id)
        pref = await asyncio.to_thread(
            deps.user_delivery_repo.get_user_category_delivery,
            user.id,
            callback_data.category_id,
        )
        enabled = pref.enabled if pref else False
        mode = pref.mode if pref else "instant"
        digest = ""
        if pref and pref.mode == "digest":
            if pref.digest_kind == "interval":
                digest = f" interval={pref.interval_minutes}m"
            elif pref.digest_kind == "daily":
                digest = f" daily={pref.daily_time_hhmm}"
        text = f"Категория: {category.name}\nEnabled: {enabled}\nMode: {mode}{digest}"
        await respond(callback, text, _build_delivery_kb(callback_data.category_id, enabled))

    @router.callback_query(UserDeliveryCb.filter(F.action == "toggle"))
    async def handle_toggle(callback: types.CallbackQuery, callback_data: UserDeliveryCb) -> None:
        user = await fetch_user(deps, callback.from_user.id)
        if not is_active(user):
            await respond(callback, "Доступ недоступен.")
            return
        pref = await asyncio.to_thread(
            deps.user_delivery_repo.get_user_category_delivery,
            user.id,
            callback_data.category_id,
        )
        enabled = not pref.enabled if pref else True
        mode = pref.mode if pref else "instant"
        digest_kind = pref.digest_kind if pref else None
        interval = pref.interval_minutes if pref else None
        daily = pref.daily_time_hhmm if pref else None
        tz = pref.timezone if pref else deps.default_tz
        await asyncio.to_thread(
            deps.user_delivery_repo.upsert_user_category_delivery,
            user.id,
            callback_data.category_id,
            enabled,
            mode,
            digest_kind,
            interval,
            daily,
            tz,
        )
        await respond(callback, "Настройки обновлены.")

    @router.callback_query(UserDeliveryCb.filter(F.action.in_({"instant", "interval_60", "daily_0900"})))
    async def handle_mode(callback: types.CallbackQuery, callback_data: UserDeliveryCb) -> None:
        user = await fetch_user(deps, callback.from_user.id)
        if not is_active(user):
            await respond(callback, "Доступ недоступен.")
            return
        pref = await asyncio.to_thread(
            deps.user_delivery_repo.get_user_category_delivery,
            user.id,
            callback_data.category_id,
        )
        enabled = pref.enabled if pref else True
        mode = "instant"
        digest_kind = None
        interval = None
        daily = None
        if callback_data.action == "interval_60":
            mode = "digest"
            digest_kind = "interval"
            interval = 60
        elif callback_data.action == "daily_0900":
            mode = "digest"
            digest_kind = "daily"
            daily = "09:00"
        tz = pref.timezone if pref else deps.default_tz
        await asyncio.to_thread(
            deps.user_delivery_repo.upsert_user_category_delivery,
            user.id,
            callback_data.category_id,
            enabled,
            mode,
            digest_kind,
            interval,
            daily,
            tz,
        )
        await respond(callback, "Настройки обновлены.")

    return router
