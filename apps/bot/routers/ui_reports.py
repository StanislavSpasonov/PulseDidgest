from __future__ import annotations

import asyncio
from datetime import datetime
from typing import List, Tuple

from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apps.bot.ui.callbacks import NavCb, ReportCb
from apps.bot.ui.common import UiDeps, fetch_user, is_admin, respond, truncate
from apps.bot.ui.list_keyboard import build_one_column_list


def _build_reports_menu() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Последние прошедшие", callback_data=ReportCb(action="pick_last_pass").pack())
    builder.button(text="❌ Последние отклонённые", callback_data=ReportCb(action="pick_last_fail").pack())
    builder.button(text="⚠️ Ошибки LLM", callback_data=ReportCb(action="llm_menu").pack())
    builder.button(text="📊 Сводка", callback_data=ReportCb(action="pick_summary").pack())
    builder.button(text="🧪 Debug toggle", callback_data=ReportCb(action="pick_debug").pack())
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(1)
    return builder.as_markup()


def _build_categories_list(categories, action: str, page: int) -> Tuple[str, types.InlineKeyboardMarkup]:
    lines = ["Выберите категорию:"]
    if not categories:
        lines.append("Категорий пока нет.")
    page_obj, kb = build_one_column_list(
        categories,
        label_fn=lambda category: category.name,
        callback_fn=lambda category: ReportCb(
            action=action, category_id=str(category.id)
        ).pack(),
        page=page,
        page_size=6,
        page_callback_fn=lambda p: ReportCb(
            action=f"{action}_page", value=str(p)
        ).pack(),
        back_cb=ReportCb(action="menu").pack(),
        home_cb=NavCb(action="home").pack(),
    )
    return "\n".join(lines), kb


def _build_limit_kb(action: str, category_id: str) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="10", callback_data=ReportCb(action=action, category_id=category_id, value="10").pack())
    builder.button(text="50", callback_data=ReportCb(action=action, category_id=category_id, value="50").pack())
    builder.button(text="⬅️ Назад", callback_data=ReportCb(action="menu").pack())
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(2)
    return builder.as_markup()


def _build_period_kb(action: str, category_id: str = "") -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="1 час", callback_data=ReportCb(action=action, category_id=category_id, value="1").pack())
    builder.button(text="24 часа", callback_data=ReportCb(action=action, category_id=category_id, value="24").pack())
    builder.button(text="7 дней", callback_data=ReportCb(action=action, category_id=category_id, value="168").pack())
    builder.button(text="⬅️ Назад", callback_data=ReportCb(action="menu").pack())
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(2)
    return builder.as_markup()


def _format_decisions(title: str, rows) -> str:
    lines = [title]
    if not rows:
        lines.append("(нет данных)")
        return "\n".join(lines)
    for decision, message in rows:
        snippet = truncate((message.text or "").replace("\n", " "), 160)
        source = f"chat {message.source_chat_id}" if getattr(message, "source_chat_id", None) else "unknown source"
        lines.append(
            f"- {decision.created_at:%Y-%m-%d %H:%M} {source} "
            f"pass={decision.passed} score={decision.score:.2f} reason={decision.reason}\n  {snippet}"
        )
    return "\n".join(lines)


def _format_llm_errors(rows) -> str:
    lines = ["LLM ошибки:"]
    if not rows:
        lines.append("(нет данных)")
        return "\n".join(lines)
    for error, category in rows:
        lines.append(
            f"- {error.created_at:%Y-%m-%d %H:%M} [{category.name}] "
            f"code={error.error_code} text={truncate(error.error_text, 120)}"
        )
    return "\n".join(lines)


def build_router(deps: UiDeps) -> Router:
    router = Router()

    async def _is_admin(user_id: int | None) -> bool:
        user = await fetch_user(deps, user_id)
        return is_admin(user, deps.admin_user_id)

    @router.callback_query(ReportCb.filter(F.action == "menu"))
    async def handle_menu(callback: types.CallbackQuery) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        await respond(callback, "Отладка/Отчёты", _build_reports_menu())

    @router.callback_query(ReportCb.filter(F.action == "pick_last_pass"))
    async def handle_pick_last_pass(callback: types.CallbackQuery) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        categories = await asyncio.to_thread(deps.admin_repo.list_categories)
        text, kb = _build_categories_list(categories, "last_pass", 0)
        await respond(callback, text, kb)

    @router.callback_query(ReportCb.filter(F.action == "pick_last_fail"))
    async def handle_pick_last_fail(callback: types.CallbackQuery) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        categories = await asyncio.to_thread(deps.admin_repo.list_categories)
        text, kb = _build_categories_list(categories, "last_fail", 0)
        await respond(callback, text, kb)

    @router.callback_query(ReportCb.filter(F.action == "pick_summary"))
    async def handle_pick_summary(callback: types.CallbackQuery) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        categories = await asyncio.to_thread(deps.admin_repo.list_categories)
        text, kb = _build_categories_list(categories, "summary_pick", 0)
        await respond(callback, text, kb)

    @router.callback_query(ReportCb.filter(F.action == "pick_debug"))
    async def handle_pick_debug(callback: types.CallbackQuery) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        categories = await asyncio.to_thread(deps.admin_repo.list_categories)
        text, kb = _build_categories_list(categories, "debug_toggle", 0)
        await respond(callback, text, kb)

    @router.callback_query(ReportCb.filter(F.action.in_(["last_pass_page", "last_fail_page", "summary_pick_page", "debug_toggle_page"])))
    async def handle_category_page(callback: types.CallbackQuery, callback_data: ReportCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        page = int(callback_data.value or "0")
        action_map = {
            "last_pass_page": "last_pass",
            "last_fail_page": "last_fail",
            "summary_pick_page": "summary_pick",
            "debug_toggle_page": "debug_toggle",
        }
        action = action_map.get(callback_data.action, "last_pass")
        categories = await asyncio.to_thread(deps.admin_repo.list_categories)
        text, kb = _build_categories_list(categories, action, page)
        await respond(callback, text, kb)

    @router.callback_query(ReportCb.filter(F.action.in_(["last_pass", "last_fail"])))
    async def handle_limit_pick(callback: types.CallbackQuery, callback_data: ReportCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        await respond(
            callback,
            "Выберите лимит:",
            _build_limit_kb(callback_data.action + "_run", callback_data.category_id),
        )

    @router.callback_query(ReportCb.filter(F.action.in_(["last_pass_run", "last_fail_run"])))
    async def handle_last_run(callback: types.CallbackQuery, callback_data: ReportCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        passed = callback_data.action == "last_pass_run"
        limit = int(callback_data.value or "10")
        category = await asyncio.to_thread(
            deps.admin_repo.get_category_by_id, callback_data.category_id
        )
        rows = await asyncio.to_thread(
            deps.admin_repo.last_decisions, category.name, passed, limit
        )
        title = f"Последние {'прошедшие' if passed else 'отклонённые'}: {category.name}"
        text = _format_decisions(title, rows)
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data=ReportCb(action="menu").pack())
        builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
        builder.adjust(2)
        await respond(callback, text, builder.as_markup())

    @router.callback_query(ReportCb.filter(F.action == "llm_menu"))
    async def handle_llm_menu(callback: types.CallbackQuery) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        await respond(callback, "Выберите период для LLM ошибок:", _build_period_kb("llm_run"))

    @router.callback_query(ReportCb.filter(F.action == "llm_run"))
    async def handle_llm_run(callback: types.CallbackQuery, callback_data: ReportCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        hours = int(callback_data.value or "24")
        rows = await asyncio.to_thread(deps.admin_repo.list_llm_errors, hours, 20)
        text = _format_llm_errors(rows)
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data=ReportCb(action="menu").pack())
        builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
        builder.adjust(2)
        await respond(callback, text, builder.as_markup())

    @router.callback_query(ReportCb.filter(F.action == "summary_pick"))
    async def handle_summary_pick(callback: types.CallbackQuery, callback_data: ReportCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        await respond(
            callback,
            "Выберите период:",
            _build_period_kb("summary_run", callback_data.category_id),
        )

    @router.callback_query(ReportCb.filter(F.action == "summary_run"))
    async def handle_summary_run(callback: types.CallbackQuery, callback_data: ReportCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        hours = int(callback_data.value or "24")
        category = await asyncio.to_thread(
            deps.admin_repo.get_category_by_id, callback_data.category_id
        )
        pass_count, fail_count, rows = await asyncio.to_thread(
            deps.admin_repo.report_category, category.name, hours, 10
        )
        title = f"Сводка {category.name} ({hours}ч): pass={pass_count} fail={fail_count}"
        text = _format_decisions(title, rows)
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data=ReportCb(action="menu").pack())
        builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
        builder.adjust(2)
        await respond(callback, text, builder.as_markup())

    @router.callback_query(ReportCb.filter(F.action == "debug_toggle"))
    async def handle_debug_toggle(callback: types.CallbackQuery, callback_data: ReportCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        try:
            category = await asyncio.to_thread(
                deps.admin_repo.get_category_by_id, callback_data.category_id
            )
            new_value = not category.debug_enabled
            await asyncio.to_thread(deps.admin_repo.set_category_debug, category.name, new_value)
            deps.logger.info("Category debug toggled via UI: %s -> %s", category.name, new_value)
            await respond(callback, f"Debug {'включён' if new_value else 'выключен'} для {category.name}.", _build_reports_menu())
        except Exception as exc:
            await respond(callback, f"Не удалось изменить debug: {exc}")

    return router
