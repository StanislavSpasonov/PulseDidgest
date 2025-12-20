from __future__ import annotations

import asyncio
from typing import List, Set, Tuple

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apps.bot.ui.callbacks import LinkCb, NavCb
from apps.bot.ui.common import UiDeps, is_admin, respond, truncate
from apps.bot.ui.pagination import paginate, page_bounds


class LinkSelectState(StatesGroup):
    add_select = State()
    remove_select = State()


def _build_categories_list(categories, page: int, per_page: int) -> Tuple[str, types.InlineKeyboardMarkup]:
    page_obj = paginate(categories, page, per_page)
    builder = InlineKeyboardBuilder()
    lines = ["Выберите категорию:"]
    if not page_obj.items:
        lines.append("Категорий пока нет.")
    for category in page_obj.items:
        builder.button(
            text=category.name,
            callback_data=LinkCb(action="category", category=category.name).pack(),
        )
    if page_obj.total_pages > 1:
        prev_page, next_page = page_bounds(page_obj.page, page_obj.total_pages)
        row = []
        if page_obj.has_prev:
            row.append(
                types.InlineKeyboardButton(
                    text="⬅️ Prev",
                    callback_data=LinkCb(action="menu", page=prev_page).pack(),
                )
            )
        if page_obj.has_next:
            row.append(
                types.InlineKeyboardButton(
                    text="Next ➡️",
                    callback_data=LinkCb(action="menu", page=next_page).pack(),
                )
            )
        if row:
            builder.row(*row)
    builder.row(
        types.InlineKeyboardButton(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    )
    return "\n".join(lines), builder.as_markup()


def _build_category_links_detail(category_name: str, links) -> Tuple[str, types.InlineKeyboardMarkup]:
    lines = [f"Источники категории {category_name}:"]
    if not links:
        lines.append("(нет привязок)")
    else:
        for link, group in links:
            lines.append(
                f"- {group.title or group.tg_chat_id} (chat_id={group.tg_chat_id})"
            )
    builder = InlineKeyboardBuilder()
    builder.button(
        text="➕ Добавить источники",
        callback_data=LinkCb(action="add", category=category_name).pack(),
    )
    builder.button(
        text="➖ Удалить источники",
        callback_data=LinkCb(action="remove", category=category_name).pack(),
    )
    builder.button(text="⬅️ Назад", callback_data=LinkCb(action="menu").pack())
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(1)
    return "\n".join(lines), builder.as_markup()


def _build_groups_select_kb(
    groups, selected: Set[int], page: int, per_page: int, mode: str, category: str
) -> Tuple[str, types.InlineKeyboardMarkup]:
    page_obj = paginate(groups, page, per_page)
    builder = InlineKeyboardBuilder()
    lines = ["Выберите группы:"]
    if not page_obj.items:
        lines.append("Нет доступных групп.")
    for group in page_obj.items:
        label = truncate(group.title or str(group.tg_chat_id), 28)
        mark = "✅" if int(group.tg_chat_id) in selected else "➕"
        builder.button(
            text=f"{mark} {label}",
            callback_data=LinkCb(
                action=f"{mode}_toggle",
                category=category,
                chat_id=int(group.tg_chat_id),
                page=page_obj.page,
            ).pack(),
        )
    if page_obj.total_pages > 1:
        prev_page, next_page = page_bounds(page_obj.page, page_obj.total_pages)
        row = []
        if page_obj.has_prev:
            row.append(
                types.InlineKeyboardButton(
                    text="⬅️ Prev",
                    callback_data=LinkCb(
                        action=f"{mode}_page", category=category, page=prev_page
                    ).pack(),
                )
            )
        if page_obj.has_next:
            row.append(
                types.InlineKeyboardButton(
                    text="Next ➡️",
                    callback_data=LinkCb(
                        action=f"{mode}_page", category=category, page=next_page
                    ).pack(),
                )
            )
        if row:
            builder.row(*row)
    builder.row(
        types.InlineKeyboardButton(
            text="Сохранить",
            callback_data=LinkCb(action=f"{mode}_save", category=category).pack(),
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=LinkCb(action="category", category=category).pack(),
        ),
        types.InlineKeyboardButton(text="🏠 Домой", callback_data=NavCb(action="home").pack()),
    )
    return "\n".join(lines), builder.as_markup()


def build_router(deps: UiDeps) -> Router:
    router = Router()

    @router.callback_query(LinkCb.filter(F.action == "menu"))
    async def handle_menu(callback: types.CallbackQuery, callback_data: LinkCb) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        categories = await asyncio.to_thread(deps.admin_repo.list_categories)
        text, kb = _build_categories_list(categories, callback_data.page, 6)
        await respond(callback, text, kb)

    @router.callback_query(LinkCb.filter(F.action == "category"))
    async def handle_category(callback: types.CallbackQuery, callback_data: LinkCb) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        try:
            _, links = await asyncio.to_thread(
                deps.admin_repo.get_category_details, callback_data.category
            )
        except Exception as exc:
            await respond(callback, f"Не удалось загрузить категорию: {exc}")
            return
        text, kb = _build_category_links_detail(callback_data.category, links)
        await respond(callback, text, kb)

    @router.callback_query(LinkCb.filter(F.action == "add"))
    async def handle_add(callback: types.CallbackQuery, callback_data: LinkCb, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        await state.set_state(LinkSelectState.add_select)
        await state.update_data(category=callback_data.category, selected_chat_ids=[])
        groups = await asyncio.to_thread(deps.admin_repo.list_groups)
        _, links = await asyncio.to_thread(
            deps.admin_repo.get_category_details, callback_data.category
        )
        bound_ids = {int(group.tg_chat_id) for _, group in links}
        available = [g for g in groups if int(g.tg_chat_id) not in bound_ids]
        text, kb = _build_groups_select_kb(
            available, set(), 0, 6, "add", callback_data.category
        )
        await respond(callback, text, kb)

    @router.callback_query(LinkCb.filter(F.action == "remove"))
    async def handle_remove(callback: types.CallbackQuery, callback_data: LinkCb, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        await state.set_state(LinkSelectState.remove_select)
        await state.update_data(category=callback_data.category, selected_chat_ids=[])
        _, links = await asyncio.to_thread(
            deps.admin_repo.get_category_details, callback_data.category
        )
        groups = [group for _, group in links]
        text, kb = _build_groups_select_kb(
            groups, set(), 0, 6, "remove", callback_data.category
        )
        await respond(callback, text, kb)

    @router.callback_query(LinkCb.filter(F.action == "add_toggle"), LinkSelectState.add_select)
    async def handle_add_toggle(callback: types.CallbackQuery, callback_data: LinkCb, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        data = await state.get_data()
        selected = set(data.get("selected_chat_ids", []))
        category = data.get("category", "")
        if callback_data.chat_id in selected:
            selected.remove(callback_data.chat_id)
        else:
            selected.add(callback_data.chat_id)
        await state.update_data(selected_chat_ids=list(selected))
        groups = await asyncio.to_thread(deps.admin_repo.list_groups)
        _, links = await asyncio.to_thread(deps.admin_repo.get_category_details, category)
        bound_ids = {int(group.tg_chat_id) for _, group in links}
        available = [g for g in groups if int(g.tg_chat_id) not in bound_ids]
        text, kb = _build_groups_select_kb(available, selected, callback_data.page, 6, "add", category)
        await respond(callback, text, kb)

    @router.callback_query(LinkCb.filter(F.action == "remove_toggle"), LinkSelectState.remove_select)
    async def handle_remove_toggle(callback: types.CallbackQuery, callback_data: LinkCb, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        data = await state.get_data()
        selected = set(data.get("selected_chat_ids", []))
        category = data.get("category", "")
        if callback_data.chat_id in selected:
            selected.remove(callback_data.chat_id)
        else:
            selected.add(callback_data.chat_id)
        await state.update_data(selected_chat_ids=list(selected))
        _, links = await asyncio.to_thread(deps.admin_repo.get_category_details, category)
        groups = [group for _, group in links]
        text, kb = _build_groups_select_kb(groups, selected, callback_data.page, 6, "remove", category)
        await respond(callback, text, kb)

    @router.callback_query(LinkCb.filter(F.action == "add_page"), LinkSelectState.add_select)
    async def handle_add_page(callback: types.CallbackQuery, callback_data: LinkCb, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        data = await state.get_data()
        selected = set(data.get("selected_chat_ids", []))
        category = data.get("category", "")
        groups = await asyncio.to_thread(deps.admin_repo.list_groups)
        _, links = await asyncio.to_thread(deps.admin_repo.get_category_details, category)
        bound_ids = {int(group.tg_chat_id) for _, group in links}
        available = [g for g in groups if int(g.tg_chat_id) not in bound_ids]
        text, kb = _build_groups_select_kb(available, selected, callback_data.page, 6, "add", category)
        await respond(callback, text, kb)

    @router.callback_query(LinkCb.filter(F.action == "remove_page"), LinkSelectState.remove_select)
    async def handle_remove_page(callback: types.CallbackQuery, callback_data: LinkCb, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        data = await state.get_data()
        selected = set(data.get("selected_chat_ids", []))
        category = data.get("category", "")
        _, links = await asyncio.to_thread(deps.admin_repo.get_category_details, category)
        groups = [group for _, group in links]
        text, kb = _build_groups_select_kb(groups, selected, callback_data.page, 6, "remove", category)
        await respond(callback, text, kb)

    @router.callback_query(LinkCb.filter(F.action == "add_save"), LinkSelectState.add_select)
    async def handle_add_save(callback: types.CallbackQuery, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        data = await state.get_data()
        category = data.get("category", "")
        selected = set(data.get("selected_chat_ids", []))
        for chat_id in selected:
            await asyncio.to_thread(deps.admin_repo.bind_category, category, chat_id)
        deps.logger.info("Bindings added via UI: category=%s count=%s", category, len(selected))
        await state.clear()
        _, links = await asyncio.to_thread(deps.admin_repo.get_category_details, category)
        text, kb = _build_category_links_detail(category, links)
        await respond(callback, "Источники добавлены.\n\n" + text, kb)

    @router.callback_query(LinkCb.filter(F.action == "remove_save"), LinkSelectState.remove_select)
    async def handle_remove_save(callback: types.CallbackQuery, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        data = await state.get_data()
        category = data.get("category", "")
        selected = set(data.get("selected_chat_ids", []))
        for chat_id in selected:
            await asyncio.to_thread(deps.admin_repo.unbind_category, category, chat_id)
        deps.logger.info("Bindings removed via UI: category=%s count=%s", category, len(selected))
        await state.clear()
        _, links = await asyncio.to_thread(deps.admin_repo.get_category_details, category)
        text, kb = _build_category_links_detail(category, links)
        await respond(callback, "Источники удалены.\n\n" + text, kb)

    return router
