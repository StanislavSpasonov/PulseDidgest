from __future__ import annotations

import asyncio
from typing import List, Set, Tuple

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apps.bot.ui.callbacks import LinkCb, LinkSelectCb, NavCb
from apps.bot.ui.common import UiDeps, is_admin, respond
from apps.bot.ui.list_keyboard import build_one_column_list


class LinkSelectState(StatesGroup):
    add_select = State()
    remove_select = State()


def _build_categories_list(categories, page: int, per_page: int) -> Tuple[str, types.InlineKeyboardMarkup]:
    lines = ["Выберите категорию:"]
    if not categories:
        lines.append("Категорий пока нет.")
    page_obj, kb = build_one_column_list(
        categories,
        label_fn=lambda category: category.name,
        callback_fn=lambda category: LinkCb(
            action="category", category_id=str(category.id)
        ).pack(),
        page=page,
        page_size=per_page,
        page_callback_fn=lambda p: LinkCb(action="menu", page=p).pack(),
        back_cb=None,
        home_cb=NavCb(action="home").pack(),
    )
    return "\n".join(lines), kb


def _build_category_links_detail(category_name: str, category_id: str, links) -> Tuple[str, types.InlineKeyboardMarkup]:
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
        callback_data=LinkCb(action="add", category_id=category_id).pack(),
    )
    builder.button(
        text="➖ Удалить источники",
        callback_data=LinkCb(action="remove", category_id=category_id).pack(),
    )
    builder.button(text="⬅️ Назад", callback_data=LinkCb(action="menu").pack())
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(1)
    return "\n".join(lines), builder.as_markup()


def _build_groups_select_kb(
    groups, selected: Set[int], page: int, per_page: int, mode: str, category_id: str
) -> Tuple[str, types.InlineKeyboardMarkup]:
    lines = ["Выберите группы:"]
    if not groups:
        lines.append("Нет доступных групп.")
    page_obj, kb = build_one_column_list(
        groups,
        label_fn=lambda group: "{} {}".format(
            "✅" if int(group.tg_chat_id) in selected else "➕",
            group.title or str(group.tg_chat_id),
        ),
        callback_fn=lambda group: LinkSelectCb(
            action=f"{mode}_toggle",
            chat_id=int(group.tg_chat_id),
            page=page,
        ).pack(),
        page=page,
        page_size=per_page,
        page_callback_fn=lambda p: LinkSelectCb(action=f"{mode}_page", page=p).pack(),
        back_cb=LinkCb(action="category", category_id=category_id).pack(),
        home_cb=NavCb(action="home").pack(),
        extra_rows=[
            [
                types.InlineKeyboardButton(
                    text="Сохранить",
                    callback_data=LinkSelectCb(action=f"{mode}_save").pack(),
                )
            ]
        ],
    )
    return "\n".join(lines), kb


def build_router(deps: UiDeps) -> Router:
    router = Router()

    @router.callback_query(LinkCb.filter(F.action == "menu"))
    async def handle_menu(
        callback: types.CallbackQuery, callback_data: LinkCb, state: FSMContext
    ) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        await state.clear()
        categories = await asyncio.to_thread(deps.admin_repo.list_categories)
        text, kb = _build_categories_list(categories, callback_data.page, 6)
        await respond(callback, text, kb)

    @router.callback_query(LinkCb.filter(F.action == "category"))
    async def handle_category(
        callback: types.CallbackQuery, callback_data: LinkCb, state: FSMContext
    ) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        await state.clear()
        try:
            category, links = await asyncio.to_thread(
                deps.admin_repo.get_category_details_by_id, callback_data.category_id
            )
        except Exception as exc:
            await respond(callback, f"Не удалось загрузить категорию: {exc}")
            return
        text, kb = _build_category_links_detail(category.name, str(category.id), links)
        await respond(callback, text, kb)

    @router.callback_query(LinkCb.filter(F.action == "add"))
    async def handle_add(callback: types.CallbackQuery, callback_data: LinkCb, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        await state.set_state(LinkSelectState.add_select)
        await state.update_data(category_id=callback_data.category_id, selected_chat_ids=[])
        groups = await asyncio.to_thread(deps.admin_repo.list_groups)
        _, links = await asyncio.to_thread(
            deps.admin_repo.get_category_details_by_id, callback_data.category_id
        )
        bound_ids = {int(group.tg_chat_id) for _, group in links}
        available = [g for g in groups if int(g.tg_chat_id) not in bound_ids]
        text, kb = _build_groups_select_kb(
            available, set(), 0, 6, "add", callback_data.category_id
        )
        await respond(callback, text, kb)

    @router.callback_query(LinkCb.filter(F.action == "remove"))
    async def handle_remove(callback: types.CallbackQuery, callback_data: LinkCb, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        await state.set_state(LinkSelectState.remove_select)
        await state.update_data(category_id=callback_data.category_id, selected_chat_ids=[])
        _, links = await asyncio.to_thread(
            deps.admin_repo.get_category_details_by_id, callback_data.category_id
        )
        groups = [group for _, group in links]
        text, kb = _build_groups_select_kb(
            groups, set(), 0, 6, "remove", callback_data.category_id
        )
        await respond(callback, text, kb)

    @router.callback_query(LinkSelectCb.filter(F.action == "add_toggle"), LinkSelectState.add_select)
    async def handle_add_toggle(callback: types.CallbackQuery, callback_data: LinkSelectCb, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        data = await state.get_data()
        selected = set(data.get("selected_chat_ids", []))
        category_id = data.get("category_id", "")
        if callback_data.chat_id in selected:
            selected.remove(callback_data.chat_id)
        else:
            selected.add(callback_data.chat_id)
        await state.update_data(selected_chat_ids=list(selected))
        groups = await asyncio.to_thread(deps.admin_repo.list_groups)
        _, links = await asyncio.to_thread(
            deps.admin_repo.get_category_details_by_id, category_id
        )
        bound_ids = {int(group.tg_chat_id) for _, group in links}
        available = [g for g in groups if int(g.tg_chat_id) not in bound_ids]
        text, kb = _build_groups_select_kb(
            available, selected, callback_data.page, 6, "add", category_id
        )
        await respond(callback, text, kb)

    @router.callback_query(LinkSelectCb.filter(F.action == "remove_toggle"), LinkSelectState.remove_select)
    async def handle_remove_toggle(callback: types.CallbackQuery, callback_data: LinkSelectCb, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        data = await state.get_data()
        selected = set(data.get("selected_chat_ids", []))
        category_id = data.get("category_id", "")
        if callback_data.chat_id in selected:
            selected.remove(callback_data.chat_id)
        else:
            selected.add(callback_data.chat_id)
        await state.update_data(selected_chat_ids=list(selected))
        _, links = await asyncio.to_thread(
            deps.admin_repo.get_category_details_by_id, category_id
        )
        groups = [group for _, group in links]
        text, kb = _build_groups_select_kb(
            groups, selected, callback_data.page, 6, "remove", category_id
        )
        await respond(callback, text, kb)

    @router.callback_query(LinkSelectCb.filter(F.action == "add_page"), LinkSelectState.add_select)
    async def handle_add_page(callback: types.CallbackQuery, callback_data: LinkSelectCb, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        data = await state.get_data()
        selected = set(data.get("selected_chat_ids", []))
        category_id = data.get("category_id", "")
        groups = await asyncio.to_thread(deps.admin_repo.list_groups)
        _, links = await asyncio.to_thread(
            deps.admin_repo.get_category_details_by_id, category_id
        )
        bound_ids = {int(group.tg_chat_id) for _, group in links}
        available = [g for g in groups if int(g.tg_chat_id) not in bound_ids]
        text, kb = _build_groups_select_kb(
            available, selected, callback_data.page, 6, "add", category_id
        )
        await respond(callback, text, kb)

    @router.callback_query(LinkSelectCb.filter(F.action == "remove_page"), LinkSelectState.remove_select)
    async def handle_remove_page(callback: types.CallbackQuery, callback_data: LinkSelectCb, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        data = await state.get_data()
        selected = set(data.get("selected_chat_ids", []))
        category_id = data.get("category_id", "")
        _, links = await asyncio.to_thread(
            deps.admin_repo.get_category_details_by_id, category_id
        )
        groups = [group for _, group in links]
        text, kb = _build_groups_select_kb(
            groups, selected, callback_data.page, 6, "remove", category_id
        )
        await respond(callback, text, kb)

    @router.callback_query(LinkSelectCb.filter(F.action == "add_save"), LinkSelectState.add_select)
    async def handle_add_save(callback: types.CallbackQuery, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        data = await state.get_data()
        category_id = data.get("category_id", "")
        selected = set(data.get("selected_chat_ids", []))
        category = await asyncio.to_thread(deps.admin_repo.get_category_by_id, category_id)
        for chat_id in selected:
            await asyncio.to_thread(deps.admin_repo.bind_category, category.name, chat_id)
        deps.logger.info("Bindings added via UI: category=%s count=%s", category.name, len(selected))
        await state.clear()
        _, links = await asyncio.to_thread(
            deps.admin_repo.get_category_details_by_id, category_id
        )
        text, kb = _build_category_links_detail(category.name, str(category.id), links)
        await respond(callback, "Источники добавлены.\n\n" + text, kb)

    @router.callback_query(LinkSelectCb.filter(F.action == "remove_save"), LinkSelectState.remove_select)
    async def handle_remove_save(callback: types.CallbackQuery, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        data = await state.get_data()
        category_id = data.get("category_id", "")
        selected = set(data.get("selected_chat_ids", []))
        category = await asyncio.to_thread(deps.admin_repo.get_category_by_id, category_id)
        for chat_id in selected:
            await asyncio.to_thread(deps.admin_repo.unbind_category, category.name, chat_id)
        deps.logger.info("Bindings removed via UI: category=%s count=%s", category.name, len(selected))
        await state.clear()
        _, links = await asyncio.to_thread(
            deps.admin_repo.get_category_details_by_id, category_id
        )
        text, kb = _build_category_links_detail(category.name, str(category.id), links)
        await respond(callback, "Источники удалены.\n\n" + text, kb)

    return router
