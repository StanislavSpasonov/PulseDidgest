from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apps.bot.ui.callbacks import DeliveryCb, NavCb
from apps.bot.ui.common import UiDeps, is_admin, respond
from apps.bot.ui.list_keyboard import build_one_column_list
from src.application.services.message_formatter import format_digest_message_html, split_message
from apps.bot.ui.reply_menu import build_menu_button_keyboard


class DeliveryTimeState(StatesGroup):
    custom_time = State()


def _build_categories_list(categories, page: int, per_page: int) -> Tuple[str, types.InlineKeyboardMarkup]:
    lines = ["Выберите категорию для доставки:"]
    if not categories:
        lines.append("Категорий пока нет.")
    page_obj, kb = build_one_column_list(
        categories,
        label_fn=lambda category: category.name,
        callback_fn=lambda category: DeliveryCb(
            action="category", category_id=str(category.id)
        ).pack(),
        page=page,
        page_size=per_page,
        page_callback_fn=lambda p: DeliveryCb(action="menu", value=str(p)).pack(),
        back_cb=None,
        home_cb=NavCb(action="home").pack(),
    )
    return "\n".join(lines), kb


def _summarize_links(links) -> Tuple[str, bool, Optional[int], Optional[str], Optional[str]]:
    if not links:
        return "нет", False, None, None, None
    modes = {link.delivery_mode for link, _ in links}
    enabled_set = {bool(link.is_enabled) for link, _ in links}
    intervals = {link.delivery_interval_minutes for link, _ in links}
    times = {link.delivery_time_local for link, _ in links}
    tzs = {link.delivery_tz for link, _ in links}
    mode = modes.pop() if len(modes) == 1 else "mixed"
    enabled = enabled_set.pop() if len(enabled_set) == 1 else False
    interval = intervals.pop() if len(intervals) == 1 else None
    time_local = times.pop() if len(times) == 1 else None
    tz = tzs.pop() if len(tzs) == 1 else None
    return mode, enabled, interval, time_local, tz


def _build_delivery_kb(category_id: str, mode: str, enabled: bool) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    instant_label = "🚀 Instant: ON" if mode == "instant" and enabled else "🚀 Instant: OFF"
    digest_label = "🧾 Digest: ON" if mode in {"hourly", "interval", "daily"} and enabled else "🧾 Digest: OFF"
    builder.button(text=instant_label, callback_data=DeliveryCb(action="instant_toggle", category_id=category_id).pack())
    builder.button(text=digest_label, callback_data=DeliveryCb(action="digest_toggle", category_id=category_id).pack())
    builder.button(text="каждый час", callback_data=DeliveryCb(action="preset", category_id=category_id, value="hourly").pack())
    builder.button(text="каждые 3 часа", callback_data=DeliveryCb(action="preset", category_id=category_id, value="interval|180").pack())
    builder.button(text="ежедневно 08:00", callback_data=DeliveryCb(action="preset", category_id=category_id, value="daily|08-00").pack())
    builder.button(text="ежедневно 18:00", callback_data=DeliveryCb(action="preset", category_id=category_id, value="daily|18-00").pack())
    builder.button(text="своё время (HH:MM)", callback_data=DeliveryCb(action="custom", category_id=category_id).pack())
    builder.button(text="📨 Отправить тестовый дайджест сейчас", callback_data=DeliveryCb(action="test_digest", category_id=category_id).pack())
    builder.button(text="⬅️ Назад", callback_data=DeliveryCb(action="menu").pack())
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(1)
    return builder.as_markup()


def _format_delivery_text(category: str, links) -> str:
    mode, enabled, interval, time_local, tz = _summarize_links(links)
    lines = [
        f"Доставка для категории {category}:",
        f"Привязок: {len(links)}",
        f"Режим: {mode}",
        f"Enabled: {'да' if enabled else 'нет'}",
    ]
    if mode == "interval":
        lines.append(f"Интервал: {interval} минут")
    if mode == "daily":
        lines.append(f"Время: {time_local} ({tz})")
    if mode == "mixed":
        lines.append("Внимание: в привязках есть разные настройки.")
    return "\n".join(lines)


def _build_digest_message(category: str, group_title: Optional[str], decisions) -> str:
    return format_digest_message_html(
        category_name=category,
        group_title=group_title,
        decisions=decisions,
    )


def build_router(deps: UiDeps) -> Router:
    router = Router()

    @router.callback_query(DeliveryCb.filter(F.action == "menu"))
    async def handle_menu(callback: types.CallbackQuery, callback_data: DeliveryCb) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        page = int(callback_data.value or "0")
        categories = await asyncio.to_thread(deps.admin_repo.list_categories)
        text, kb = _build_categories_list(categories, page, 6)
        await respond(callback, text, kb)

    @router.callback_query(DeliveryCb.filter(F.action == "category"))
    async def handle_category(callback: types.CallbackQuery, callback_data: DeliveryCb) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        try:
            category = await asyncio.to_thread(
                deps.admin_repo.get_category_by_id, callback_data.category_id
            )
            links = await asyncio.to_thread(
                deps.admin_repo.get_delivery_info, category.name
            )
        except Exception as exc:
            await respond(callback, f"Не удалось загрузить доставку: {exc}")
            return
        text = _format_delivery_text(category.name, links)
        mode, enabled, _, _, _ = _summarize_links(links)
        await respond(callback, text, _build_delivery_kb(callback_data.category_id, mode, enabled))

    @router.callback_query(DeliveryCb.filter(F.action == "instant_toggle"))
    async def handle_instant_toggle(callback: types.CallbackQuery, callback_data: DeliveryCb) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        category = await asyncio.to_thread(
            deps.admin_repo.get_category_by_id, callback_data.category_id
        )
        links = await asyncio.to_thread(deps.admin_repo.get_delivery_info, category.name)
        mode, enabled, _, _, _ = _summarize_links(links)
        new_enabled = not (mode == "instant" and enabled)
        await asyncio.to_thread(
            deps.admin_repo.set_delivery_for_category,
            category.name,
            "instant",
            None,
            None,
            deps.default_tz,
            new_enabled,
        )
        deps.logger.info("Delivery instant toggled via UI: category=%s enabled=%s", category.name, new_enabled)
        await handle_category(callback, DeliveryCb(action="category", category_id=callback_data.category_id))

    @router.callback_query(DeliveryCb.filter(F.action == "digest_toggle"))
    async def handle_digest_toggle(callback: types.CallbackQuery, callback_data: DeliveryCb) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        category = await asyncio.to_thread(
            deps.admin_repo.get_category_by_id, callback_data.category_id
        )
        links = await asyncio.to_thread(deps.admin_repo.get_delivery_info, category.name)
        mode, enabled, interval, time_local, _ = _summarize_links(links)
        is_digest = mode in {"hourly", "interval", "daily"}
        new_enabled = not (is_digest and enabled)
        new_mode = mode if is_digest else "hourly"
        await asyncio.to_thread(
            deps.admin_repo.set_delivery_for_category,
            category.name,
            new_mode,
            interval if new_mode == "interval" else None,
            time_local if new_mode == "daily" else None,
            deps.default_tz,
            new_enabled,
        )
        deps.logger.info("Delivery digest toggled via UI: category=%s enabled=%s", category.name, new_enabled)
        await handle_category(callback, DeliveryCb(action="category", category_id=callback_data.category_id))

    @router.callback_query(DeliveryCb.filter(F.action == "preset"))
    async def handle_preset(callback: types.CallbackQuery, callback_data: DeliveryCb) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        category = await asyncio.to_thread(
            deps.admin_repo.get_category_by_id, callback_data.category_id
        )
        value = callback_data.value
        mode = value
        interval = None
        time_local = None
        if value.startswith("interval|"):
            mode = "interval"
            interval = int(value.split("|", 1)[1])
        if value.startswith("daily|"):
            mode = "daily"
            time_local = value.split("|", 1)[1].replace("-", ":")
        await asyncio.to_thread(
            deps.admin_repo.set_delivery_for_category,
            category.name,
            mode,
            interval,
            time_local,
            deps.default_tz,
            True,
        )
        deps.logger.info("Delivery preset set via UI: category=%s mode=%s", category.name, mode)
        await handle_category(callback, DeliveryCb(action="category", category_id=callback_data.category_id))

    @router.callback_query(DeliveryCb.filter(F.action == "custom"))
    async def handle_custom(callback: types.CallbackQuery, callback_data: DeliveryCb, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        await state.set_state(DeliveryTimeState.custom_time)
        await state.update_data(category_id=callback_data.category_id)
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data=DeliveryCb(action="category", category_id=callback_data.category_id).pack())
        builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
        builder.adjust(2)
        await respond(callback, "Введите время в формате HH:MM:", builder.as_markup())

    @router.message(DeliveryTimeState.custom_time)
    async def handle_custom_time(message: types.Message, state: FSMContext) -> None:
        if not is_admin(message.from_user.id if message.from_user else None, deps.admin_user_id):
            await message.answer("Меню доступно только администраторам.")
            await state.clear()
            return
        data = await state.get_data()
        category_id = data.get("category_id", "")
        value = (message.text or "").strip()
        if ":" not in value:
            await message.answer("Неверный формат. Пример: 08:00")
            return
        category = await asyncio.to_thread(
            deps.admin_repo.get_category_by_id, category_id
        )
        await asyncio.to_thread(
            deps.admin_repo.set_delivery_for_category,
            category.name,
            "daily",
            None,
            value,
            deps.default_tz,
            True,
        )
        deps.logger.info("Delivery custom time set via UI: category=%s time=%s", category.name, value)
        await state.clear()
        links = await asyncio.to_thread(deps.admin_repo.get_delivery_info, category.name)
        text = _format_delivery_text(category.name, links)
        mode, enabled, _, _, _ = _summarize_links(links)
        await message.answer(text, reply_markup=_build_delivery_kb(category_id, mode, enabled))

    @router.callback_query(DeliveryCb.filter(F.action == "test_digest"))
    async def handle_test_digest(callback: types.CallbackQuery, callback_data: DeliveryCb) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        try:
            category, links = await asyncio.to_thread(
                deps.admin_repo.get_category_details_by_id, callback_data.category_id
            )
        except Exception as exc:
            await respond(callback, f"Не удалось загрузить категорию: {exc}")
            return
        if not links:
            await respond(callback, "Нет привязанных групп для дайджеста.")
            return
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        sent = 0
        for link, group in links:
            decisions = await asyncio.to_thread(
                deps.delivery_repo.fetch_recent_passed_decisions,
                str(category.id),
                int(group.tg_chat_id),
                since,
                30,
            )
            if not decisions:
                continue
            payload = _build_digest_message(category.name, group.title, decisions)
            for chunk in split_message(payload):
                await callback.message.bot.send_message(
                    callback.message.chat.id,
                    chunk,
                    parse_mode="HTML",
                    reply_markup=build_menu_button_keyboard(),
                )
            sent += 1
        if sent == 0:
            await respond(callback, "За последние 24 часа нет материалов для дайджеста.")
        else:
            await respond(callback, f"Отправлено тестовых дайджестов: {sent}")

    return router
