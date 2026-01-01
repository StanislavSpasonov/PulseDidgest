from __future__ import annotations

import asyncio

from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apps.bot.ui.callbacks import AccessCb, NavCb
from apps.bot.ui.common import UiDeps, fetch_user, is_admin, respond
from apps.bot.ui.list_keyboard import build_one_column_list


def _build_categories_list(categories, page: int):
    page_obj, kb = build_one_column_list(
        categories,
        label_fn=lambda category: category.name,
        callback_fn=lambda category: AccessCb(action="category", category_id=str(category.id)).pack(),
        page=page,
        page_size=6,
        page_callback_fn=lambda p: AccessCb(action="page", page=p).pack(),
        back_cb=NavCb(action="home").pack(),
        home_cb=NavCb(action="home").pack(),
    )
    return page_obj, kb


def _build_user_access_list(users, category_id: str, permissions: dict[str, str], owner_id: str | None, page: int):
    def _label(user) -> str:
        if user.role == "admin":
            return f"@{user.username or 'unknown'} (admin)"
        if owner_id and user.id == owner_id:
            return f"@{user.username or 'unknown'} (owner)"
        return f"@{user.username or 'unknown'} ({permissions.get(user.id, 'no')})"

    page_obj, kb = build_one_column_list(
        users,
        label_fn=_label,
        callback_fn=lambda user: AccessCb(action="user", category_id=category_id, user_id=str(user.id)).pack(),
        page=page,
        page_size=6,
        page_callback_fn=lambda p: AccessCb(action="user_page", category_id=category_id, page=p).pack(),
        back_cb=AccessCb(action="menu").pack(),
        home_cb=NavCb(action="home").pack(),
    )
    return page_obj, kb


def _build_access_actions(category_id: str, user_id: str, locked: bool) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not locked:
        builder.button(text="Use", callback_data=AccessCb(action="grant", category_id=category_id, user_id=user_id, value="use").pack())
        builder.button(text="Edit", callback_data=AccessCb(action="grant", category_id=category_id, user_id=user_id, value="edit").pack())
        builder.button(text="Revoke", callback_data=AccessCb(action="revoke", category_id=category_id, user_id=user_id).pack())
    builder.button(text="⬅️ Назад", callback_data=AccessCb(action="category", category_id=category_id).pack())
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(1)
    return builder.as_markup()


def build_router(deps: UiDeps) -> Router:
    router = Router()

    async def _is_admin(user_id: int | None) -> bool:
        user = await fetch_user(deps, user_id)
        return is_admin(user, deps.admin_user_id)

    @router.callback_query(AccessCb.filter(F.action == "menu"))
    async def handle_menu(callback: types.CallbackQuery) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        categories = await asyncio.to_thread(deps.admin_repo.list_categories)
        if not categories:
            await respond(callback, "Категорий нет.")
            return
        _, kb = _build_categories_list(categories, 0)
        await respond(callback, "Выберите категорию:", kb)

    @router.callback_query(AccessCb.filter(F.action == "page"))
    async def handle_page(callback: types.CallbackQuery, callback_data: AccessCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        categories = await asyncio.to_thread(deps.admin_repo.list_categories)
        if not categories:
            await respond(callback, "Категорий нет.")
            return
        _, kb = _build_categories_list(categories, callback_data.page)
        await respond(callback, "Выберите категорию:", kb)

    @router.callback_query(AccessCb.filter(F.action == "category"))
    async def handle_category(callback: types.CallbackQuery, callback_data: AccessCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        if not callback_data.category_id:
            await respond(callback, "Категория не найдена.")
            return
        category = await asyncio.to_thread(deps.admin_repo.get_category_by_id, callback_data.category_id)
        users = await asyncio.to_thread(deps.user_repo.list_users, "active")
        entries = await asyncio.to_thread(deps.access_repo.list_acl_entries, callback_data.category_id)
        permissions = {entry.user_id: entry.permission for entry in entries}
        _, kb = _build_user_access_list(users, callback_data.category_id, permissions, str(category.owner_user_id) if category.owner_user_id else None, 0)
        await respond(callback, f"Доступ к категории: {category.name}", kb)

    @router.callback_query(AccessCb.filter(F.action == "user_page"))
    async def handle_user_page(callback: types.CallbackQuery, callback_data: AccessCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        category = await asyncio.to_thread(deps.admin_repo.get_category_by_id, callback_data.category_id)
        users = await asyncio.to_thread(deps.user_repo.list_users, "active")
        entries = await asyncio.to_thread(deps.access_repo.list_acl_entries, callback_data.category_id)
        permissions = {entry.user_id: entry.permission for entry in entries}
        _, kb = _build_user_access_list(users, callback_data.category_id, permissions, str(category.owner_user_id) if category.owner_user_id else None, callback_data.page)
        await respond(callback, f"Доступ к категории: {category.name}", kb)

    @router.callback_query(AccessCb.filter(F.action == "user"))
    async def handle_user(callback: types.CallbackQuery, callback_data: AccessCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        user = await asyncio.to_thread(deps.user_repo.get_by_id, callback_data.user_id)
        if not user:
            await respond(callback, "Пользователь не найден.")
            return
        category = await asyncio.to_thread(deps.admin_repo.get_category_by_id, callback_data.category_id)
        entries = await asyncio.to_thread(deps.access_repo.list_acl_entries, callback_data.category_id)
        permissions = {entry.user_id: entry.permission for entry in entries}
        permission = permissions.get(callback_data.user_id, "no")
        locked = user.role == "admin" or (category.owner_user_id and str(category.owner_user_id) == user.id)
        info = f"@{user.username or 'unknown'}\nrole={user.role}\naccess={permission}"
        if locked:
            info += "\n(implicit access)"
        await respond(callback, info, _build_access_actions(callback_data.category_id, callback_data.user_id, locked))

    @router.callback_query(AccessCb.filter(F.action == "grant"))
    async def handle_grant(callback: types.CallbackQuery, callback_data: AccessCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        if not callback_data.value:
            await respond(callback, "Нет permission.")
            return
        await asyncio.to_thread(
            deps.access_repo.grant_access,
            callback_data.category_id,
            callback_data.user_id,
            callback_data.value,
        )
        await respond(callback, "Доступ обновлён.")

    @router.callback_query(AccessCb.filter(F.action == "revoke"))
    async def handle_revoke(callback: types.CallbackQuery, callback_data: AccessCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        await asyncio.to_thread(
            deps.access_repo.revoke_access,
            callback_data.category_id,
            callback_data.user_id,
        )
        await respond(callback, "Доступ отозван.")

    return router
