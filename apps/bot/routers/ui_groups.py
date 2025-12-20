from __future__ import annotations

import asyncio
from typing import List, Set, Tuple

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apps.bot.ui.callbacks import GroupCb, LinkCb, NavCb
from apps.bot.ui.common import UiDeps, format_chat_line, is_admin, respond, truncate
from apps.bot.ui.pagination import paginate, page_bounds


class GroupSearchState(StatesGroup):
    query = State()


def _build_groups_menu() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Мои чаты", callback_data=GroupCb(action="my", page=0).pack())
    builder.button(text="🔎 Найти по имени", callback_data=GroupCb(action="search").pack())
    builder.button(text="📌 Показать зарегистрированные", callback_data=GroupCb(action="registered", page=0).pack())
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(1)
    return builder.as_markup()


def _format_dialogs_list(
    chats,
    registered_ids: Set[int],
    page: int,
    per_page: int,
    title: str,
    list_action: str,
) -> Tuple[str, types.InlineKeyboardMarkup]:
    page_obj = paginate(chats, page, per_page)
    builder = InlineKeyboardBuilder()
    lines = [title]
    if not page_obj.items:
        lines.append("Ничего не найдено.")
    for chat in page_obj.items:
        label = truncate(chat.title or chat.username or str(chat.chat_id), 28)
        if chat.chat_id in registered_ids:
            button_text = f"✅ {label}"
            callback = GroupCb(action="detail", chat_id=int(chat.chat_id)).pack()
        else:
            button_text = f"➕ {label}"
            callback = GroupCb(action="add", chat_id=int(chat.chat_id)).pack()
        builder.button(text=button_text, callback_data=callback)
    if page_obj.total_pages > 1:
        prev_page, next_page = page_bounds(page_obj.page, page_obj.total_pages)
        row = []
        if page_obj.has_prev:
            row.append(
                types.InlineKeyboardButton(
                    text="⬅️ Prev",
                    callback_data=GroupCb(action=list_action, page=prev_page).pack(),
                )
            )
        if page_obj.has_next:
            row.append(
                types.InlineKeyboardButton(
                    text="Next ➡️",
                    callback_data=GroupCb(action=list_action, page=next_page).pack(),
                )
            )
        if row:
            builder.row(*row)
    builder.row(
        types.InlineKeyboardButton(text="⬅️ Назад", callback_data=GroupCb(action="menu").pack()),
        types.InlineKeyboardButton(text="🏠 Домой", callback_data=NavCb(action="home").pack()),
    )
    return "\n".join(lines), builder.as_markup()


def _format_registered_list(groups, page: int, per_page: int) -> Tuple[str, types.InlineKeyboardMarkup]:
    page_obj = paginate(groups, page, per_page)
    builder = InlineKeyboardBuilder()
    lines = ["Зарегистрированные группы:"]
    if not page_obj.items:
        lines.append("Пока нет зарегистрированных групп.")
    for group in page_obj.items:
        label = truncate(group.title or str(group.tg_chat_id), 28)
        builder.button(
            text=label,
            callback_data=GroupCb(action="detail", chat_id=int(group.tg_chat_id)).pack(),
        )
    if page_obj.total_pages > 1:
        prev_page, next_page = page_bounds(page_obj.page, page_obj.total_pages)
        row = []
        if page_obj.has_prev:
            row.append(
                types.InlineKeyboardButton(
                    text="⬅️ Prev",
                    callback_data=GroupCb(action="registered", page=prev_page).pack(),
                )
            )
        if page_obj.has_next:
            row.append(
                types.InlineKeyboardButton(
                    text="Next ➡️",
                    callback_data=GroupCb(action="registered", page=next_page).pack(),
                )
            )
        if row:
            builder.row(*row)
    builder.row(
        types.InlineKeyboardButton(text="⬅️ Назад", callback_data=GroupCb(action="menu").pack()),
        types.InlineKeyboardButton(text="🏠 Домой", callback_data=NavCb(action="home").pack()),
    )
    return "\n".join(lines), builder.as_markup()


def _build_bind_category_kb(categories, chat_id: int) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.button(
            text=category.name,
            callback_data=LinkCb(action="bind", category=category.name, chat_id=chat_id).pack(),
        )
    builder.button(text="Пропустить", callback_data=GroupCb(action="menu").pack())
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(1)
    return builder.as_markup()


def _build_group_detail_kb(chat_id: int) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🔗 Привязать к категории",
        callback_data=GroupCb(action="bind_pick", chat_id=chat_id).pack(),
    )
    builder.button(
        text="🗑 Удалить",
        callback_data=GroupCb(action="delete_confirm", chat_id=chat_id).pack(),
    )
    builder.button(text="⬅️ Назад", callback_data=GroupCb(action="registered", page=0).pack())
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(1)
    return builder.as_markup()


def build_router(deps: UiDeps) -> Router:
    router = Router()

    @router.callback_query(GroupCb.filter(F.action == "menu"))
    async def handle_menu(callback: types.CallbackQuery, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        await state.clear()
        await respond(callback, "Группы (источники)", _build_groups_menu())

    @router.callback_query(GroupCb.filter(F.action == "my"))
    async def handle_my_chats(callback: types.CallbackQuery, callback_data: GroupCb) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        try:
            chats = await deps.list_chats_use_case.execute(limit=deps.telethon_dialog_limit)
        except Exception as exc:
            deps.logger.exception("Telethon list failed: %s", exc)
            await respond(callback, f"Не удалось получить список чатов: {exc}")
            return
        groups = await asyncio.to_thread(deps.admin_repo.list_groups)
        registered_ids = {int(group.tg_chat_id) for group in groups}
        text, kb = _format_dialogs_list(
            chats,
            registered_ids,
            callback_data.page,
            6,
            "Мои чаты:",
            "my",
        )
        await respond(callback, text, kb)

    @router.callback_query(GroupCb.filter(F.action == "registered"))
    async def handle_registered(callback: types.CallbackQuery, callback_data: GroupCb) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        groups = await asyncio.to_thread(deps.admin_repo.list_groups)
        text, kb = _format_registered_list(groups, callback_data.page, 6)
        await respond(callback, text, kb)

    @router.callback_query(GroupCb.filter(F.action == "search"))
    async def handle_search(callback: types.CallbackQuery, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        await state.set_state(GroupSearchState.query)
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data=GroupCb(action="menu").pack())
        builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
        builder.adjust(2)
        await respond(callback, "Введите часть названия или username для поиска:", builder.as_markup())

    @router.message(GroupSearchState.query)
    async def handle_search_query(message: types.Message, state: FSMContext) -> None:
        if not is_admin(message.from_user.id if message.from_user else None, deps.admin_user_id):
            await message.answer("Меню доступно только администраторам.")
            await state.clear()
            return
        query = (message.text or "").strip()
        if not query:
            await message.answer("Введите непустой запрос.")
            return
        await state.update_data(query=query)
        try:
            chats = await deps.search_chats_use_case.execute(
                query, limit=deps.telethon_dialog_limit
            )
        except Exception as exc:
            deps.logger.exception("Telethon search failed: %s", exc)
            await message.answer(f"Не удалось выполнить поиск: {exc}")
            return
        groups = await asyncio.to_thread(deps.admin_repo.list_groups)
        registered_ids = {int(group.tg_chat_id) for group in groups}
        text, kb = _format_dialogs_list(
            chats,
            registered_ids,
            0,
            6,
            f"Результаты поиска: {query}",
            "search_page",
        )
        await message.answer(text, reply_markup=kb)

    @router.callback_query(GroupCb.filter(F.action == "search_page"), GroupSearchState.query)
    async def handle_search_page(
        callback: types.CallbackQuery, callback_data: GroupCb, state: FSMContext
    ) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        data = await state.get_data()
        query = data.get("query", "")
        try:
            chats = await deps.search_chats_use_case.execute(
                query, limit=deps.telethon_dialog_limit
            )
        except Exception as exc:
            deps.logger.exception("Telethon search failed: %s", exc)
            await respond(callback, f"Не удалось выполнить поиск: {exc}")
            return
        groups = await asyncio.to_thread(deps.admin_repo.list_groups)
        registered_ids = {int(group.tg_chat_id) for group in groups}
        text, kb = _format_dialogs_list(
            chats,
            registered_ids,
            callback_data.page,
            6,
            f"Результаты поиска: {query}",
            "search_page",
        )
        await respond(callback, text, kb)

    @router.callback_query(GroupCb.filter(F.action == "add"))
    async def handle_add(callback: types.CallbackQuery, callback_data: GroupCb) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        try:
            chats = await deps.list_chats_use_case.execute(limit=deps.telethon_dialog_limit)
        except Exception as exc:
            deps.logger.exception("Telethon list failed: %s", exc)
            await respond(callback, f"Не удалось получить список чатов: {exc}")
            return
        chat = next((c for c in chats if int(c.chat_id) == callback_data.chat_id), None)
        if not chat:
            await respond(callback, "Не удалось найти чат в Telethon.")
            return
        try:
            await asyncio.to_thread(
                deps.admin_repo.register_group, chat.chat_id, chat.title or chat.username
            )
            deps.logger.info("Group registered via UI: %s", chat.chat_id)
        except Exception as exc:
            await respond(callback, f"Не удалось добавить группу: {exc}")
            return
        categories = await asyncio.to_thread(deps.admin_repo.list_categories)
        text = (
            "Группа добавлена.\n"
            f"{format_chat_line(chat)}\n\n"
            "Привязать к категории?"
        )
        await respond(callback, text, _build_bind_category_kb(categories, chat.chat_id))

    @router.callback_query(LinkCb.filter(F.action == "bind"))
    async def handle_bind_from_group(
        callback: types.CallbackQuery, callback_data: LinkCb
    ) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        try:
            await asyncio.to_thread(
                deps.admin_repo.bind_category,
                callback_data.category,
                callback_data.chat_id,
            )
            deps.logger.info(
                "Binding created via UI: category=%s chat_id=%s",
                callback_data.category,
                callback_data.chat_id,
            )
            await respond(
                callback,
                f"Привязка создана: {callback_data.category}",
                _build_groups_menu(),
            )
        except Exception as exc:
            await respond(callback, f"Не удалось привязать: {exc}")

    @router.callback_query(GroupCb.filter(F.action == "detail"))
    async def handle_detail(callback: types.CallbackQuery, callback_data: GroupCb) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        group = None
        groups = await asyncio.to_thread(deps.admin_repo.list_groups)
        for item in groups:
            if int(item.tg_chat_id) == callback_data.chat_id:
                group = item
                break
        if not group:
            await respond(callback, "Группа не найдена.")
            return
        username = None
        try:
            chats = await deps.list_chats_use_case.execute(limit=deps.telethon_dialog_limit)
            match = next((c for c in chats if int(c.chat_id) == callback_data.chat_id), None)
            if match:
                username = match.username
        except Exception:
            username = None
        lines = [
            "Группа:",
            f"Название: {group.title or '<без названия>'}",
            f"Username: @{username}" if username else "Username: <нет>",
            f"chat_id: {group.tg_chat_id}",
        ]
        await respond(callback, "\n".join(lines), _build_group_detail_kb(int(group.tg_chat_id)))

    @router.callback_query(GroupCb.filter(F.action == "bind_pick"))
    async def handle_bind_pick(callback: types.CallbackQuery, callback_data: GroupCb) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        categories = await asyncio.to_thread(deps.admin_repo.list_categories)
        if not categories:
            await respond(callback, "Сначала создайте категорию.", _build_groups_menu())
            return
        await respond(
            callback,
            "Выберите категорию для привязки:",
            _build_bind_category_kb(categories, callback_data.chat_id),
        )

    @router.callback_query(GroupCb.filter(F.action == "delete_confirm"))
    async def handle_delete_confirm(callback: types.CallbackQuery, callback_data: GroupCb) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        builder = InlineKeyboardBuilder()
        builder.button(
            text="Да, удалить",
            callback_data=GroupCb(action="delete_yes", chat_id=callback_data.chat_id).pack(),
        )
        builder.button(text="Отмена", callback_data=GroupCb(action="detail", chat_id=callback_data.chat_id).pack())
        builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
        builder.adjust(1)
        await respond(callback, "Удалить зарегистрированную группу?", builder.as_markup())

    @router.callback_query(GroupCb.filter(F.action == "delete_yes"))
    async def handle_delete_yes(callback: types.CallbackQuery, callback_data: GroupCb) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        try:
            await asyncio.to_thread(deps.admin_repo.delete_group, callback_data.chat_id)
            deps.logger.info("Group deleted via UI: %s", callback_data.chat_id)
            await respond(callback, "Группа удалена.", _build_groups_menu())
        except Exception as exc:
            await respond(callback, f"Не удалось удалить группу: {exc}")

    return router
