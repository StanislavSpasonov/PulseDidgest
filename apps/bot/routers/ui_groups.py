from __future__ import annotations

import asyncio
from typing import List, Set, Tuple

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apps.bot.ui.callbacks import GroupCb, LinkCb, NavCb
from apps.bot.ui.common import UiDeps, fetch_user, format_chat_line, is_admin, is_power, respond
from apps.bot.ui.list_keyboard import build_one_column_list
from src.infrastructure.telegram_client.dialog_service import TelethonUnauthorizedError


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
    lines = [title]
    if not chats:
        lines.append("Ничего не найдено.")
    page_obj, kb = build_one_column_list(
        chats,
        label_fn=lambda chat: "{} {}".format(
            "✅" if chat.chat_id in registered_ids else "➕",
            _format_chat_label(chat),
        ),
        callback_fn=lambda chat: (
            GroupCb(action="detail", chat_id=int(chat.chat_id)).pack()
            if chat.chat_id in registered_ids
            else GroupCb(action="add", chat_id=int(chat.chat_id)).pack()
        ),
        page=page,
        page_size=per_page,
        page_callback_fn=lambda p: GroupCb(action=list_action, page=p).pack(),
        back_cb=GroupCb(action="menu").pack(),
        home_cb=NavCb(action="home").pack(),
    )
    return "\n".join(lines), kb


def _format_registered_list(groups, page: int, per_page: int) -> Tuple[str, types.InlineKeyboardMarkup]:
    lines = ["Зарегистрированные группы:"]
    if not groups:
        lines.append("Пока нет зарегистрированных групп.")
    page_obj, kb = build_one_column_list(
        groups,
        label_fn=lambda group: group.title or str(group.tg_chat_id),
        callback_fn=lambda group: GroupCb(
            action="detail", chat_id=int(group.tg_chat_id)
        ).pack(),
        page=page,
        page_size=per_page,
        page_callback_fn=lambda p: GroupCb(action="registered", page=p).pack(),
        back_cb=GroupCb(action="menu").pack(),
        home_cb=NavCb(action="home").pack(),
    )
    return "\n".join(lines), kb


def _build_bind_category_kb(categories, chat_id: int) -> types.InlineKeyboardMarkup:
    _, kb = build_one_column_list(
        categories,
        label_fn=lambda category: category.name,
        callback_fn=lambda category: LinkCb(
            action="bind", category_id=str(category.id), chat_id=chat_id
        ).pack(),
        page=0,
        page_size=len(categories) or 1,
        show_prev_next=False,
        show_back_home=True,
        back_cb=None,
        home_cb=NavCb(action="home").pack(),
        extra_rows=[
            [
                types.InlineKeyboardButton(
                    text="Пропустить",
                    callback_data=GroupCb(action="menu").pack(),
                )
            ]
        ],
    )
    return kb


def _format_chat_label(chat) -> str:
    title = chat.title or f"@{chat.username}" if chat.username else str(chat.chat_id)
    if chat.username and chat.title:
        return f"{title} (@{chat.username})"
    return title


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


def _telethon_auth_required_text() -> str:
    return "Telethon не авторизован. Запустите collector один раз для авторизации."


def build_router(deps: UiDeps) -> Router:
    router = Router()

    async def _is_admin_or_power(user_id: int | None) -> bool:
        user = await fetch_user(deps, user_id)
        return bool(user and (is_admin(user, deps.admin_user_id) or is_power(user, deps.admin_user_id)))


    @router.callback_query(GroupCb.filter(F.action == "menu"))
    async def handle_menu(callback: types.CallbackQuery, state: FSMContext) -> None:
        if not await _is_admin_or_power(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        await state.clear()
        await respond(callback, "Группы (источники)", _build_groups_menu())

    @router.callback_query(GroupCb.filter(F.action == "my"))
    async def handle_my_chats(callback: types.CallbackQuery, callback_data: GroupCb) -> None:
        if not await _is_admin_or_power(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        try:
            chats = await deps.list_chats_use_case.execute(limit=deps.telethon_dialog_limit)
        except TelethonUnauthorizedError as exc:
            deps.logger.warning("Telethon not authorized: %s", exc)
            await respond(callback, _telethon_auth_required_text())
            return
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
        if not await _is_admin_or_power(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        groups = await asyncio.to_thread(deps.admin_repo.list_groups)
        text, kb = _format_registered_list(groups, callback_data.page, 6)
        await respond(callback, text, kb)

    @router.callback_query(GroupCb.filter(F.action == "search"))
    async def handle_search(callback: types.CallbackQuery, state: FSMContext) -> None:
        if not await _is_admin_or_power(callback.from_user.id):
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
        if not await _is_admin_or_power(message.from_user.id if message.from_user else None):
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
        except TelethonUnauthorizedError as exc:
            deps.logger.warning("Telethon not authorized: %s", exc)
            await message.answer(_telethon_auth_required_text())
            return
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
        if not await _is_admin_or_power(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        data = await state.get_data()
        query = data.get("query", "")
        try:
            chats = await deps.search_chats_use_case.execute(
                query, limit=deps.telethon_dialog_limit
            )
        except TelethonUnauthorizedError as exc:
            deps.logger.warning("Telethon not authorized: %s", exc)
            await respond(callback, _telethon_auth_required_text())
            return
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
        if not await _is_admin_or_power(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        try:
            chats = await deps.list_chats_use_case.execute(limit=deps.telethon_dialog_limit)
        except TelethonUnauthorizedError as exc:
            deps.logger.warning("Telethon not authorized: %s", exc)
            await respond(callback, _telethon_auth_required_text())
            return
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
                deps.admin_repo.register_group,
                chat.chat_id,
                chat.title or chat.username,
                chat.username,
            )
            deps.logger.info("Group registered via UI: %s", chat.chat_id)
        except Exception as exc:
            await respond(callback, f"Не удалось добавить группу: {exc}")
            return
        user = await fetch_user(deps, callback.from_user.id)
        if user and not is_admin(user, deps.admin_user_id):
            categories = await asyncio.to_thread(
                deps.access_repo.list_editable_categories_for_user,
                user.id,
            )
        else:
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
        if not await _is_admin_or_power(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        try:
            category = await asyncio.to_thread(
                deps.admin_repo.get_category_by_id, callback_data.category_id
            )
            user = await fetch_user(deps, callback.from_user.id)
            if user and not is_admin(user, deps.admin_user_id):
                permission = await asyncio.to_thread(
                    deps.access_repo.get_user_permission,
                    callback_data.category_id,
                    user.id,
                )
                is_owner = bool(category.owner_user_id and str(category.owner_user_id) == user.id)
                if not (is_owner or permission == "edit"):
                    await respond(callback, "Нет доступа к категории.")
                    return
            await asyncio.to_thread(
                deps.admin_repo.bind_category,
                category.name,
                callback_data.chat_id,
            )
            deps.logger.info(
                "Binding created via UI: category=%s chat_id=%s",
                category.name,
                callback_data.chat_id,
            )
            await respond(
                callback,
                f"Привязка создана: {category.name}",
                _build_groups_menu(),
            )
        except Exception as exc:
            await respond(callback, f"Не удалось привязать: {exc}")

    @router.callback_query(GroupCb.filter(F.action == "detail"))
    async def handle_detail(callback: types.CallbackQuery, callback_data: GroupCb) -> None:
        if not await _is_admin_or_power(callback.from_user.id):
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
        if not await _is_admin_or_power(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        user = await fetch_user(deps, callback.from_user.id)
        if user and not is_admin(user, deps.admin_user_id):
            categories = await asyncio.to_thread(
                deps.access_repo.list_editable_categories_for_user,
                user.id,
            )
        else:
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
        if not await _is_admin_or_power(callback.from_user.id):
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
        if not await _is_admin_or_power(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        try:
            await asyncio.to_thread(deps.admin_repo.delete_group, callback_data.chat_id)
            deps.logger.info("Group deleted via UI: %s", callback_data.chat_id)
            await respond(callback, "Группа удалена.", _build_groups_menu())
        except Exception as exc:
            await respond(callback, f"Не удалось удалить группу: {exc}")

    return router
