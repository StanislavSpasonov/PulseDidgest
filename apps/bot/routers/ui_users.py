from __future__ import annotations

import asyncio

from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apps.bot.ui.callbacks import NavCb, UserCb
from apps.bot.ui.common import UiDeps, fetch_user, is_admin, respond
from apps.bot.ui.list_keyboard import build_one_column_list


def _build_user_list(users, page: int):
    page_obj, kb = build_one_column_list(
        users,
        label_fn=lambda user: f"{user.first_name or ''} @{user.username or 'unknown'} ({user.status})",
        callback_fn=lambda user: UserCb(action="open", user_id=str(user.id)).pack(),
        page=page,
        page_size=6,
        page_callback_fn=lambda p: UserCb(action="page", page=p).pack(),
        back_cb=NavCb(action="home").pack(),
        home_cb=NavCb(action="home").pack(),
    )
    return page_obj, kb


def _build_user_actions(user_id: str) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Approve", callback_data=UserCb(action="approve", user_id=user_id).pack())
    builder.button(text="⛔️ Block", callback_data=UserCb(action="block", user_id=user_id).pack())
    builder.button(text="Role: user", callback_data=UserCb(action="role_user", user_id=user_id).pack())
    builder.button(text="Role: power", callback_data=UserCb(action="role_power", user_id=user_id).pack())
    builder.button(text="Role: admin", callback_data=UserCb(action="role_admin", user_id=user_id).pack())
    builder.button(text="⬅️ Назад", callback_data=UserCb(action="menu").pack())
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(1)
    return builder.as_markup()


def build_router(deps: UiDeps) -> Router:
    router = Router()

    async def _is_admin(user_id: int | None) -> bool:
        user = await fetch_user(deps, user_id)
        return is_admin(user, deps.admin_user_id)

    @router.callback_query(UserCb.filter(F.action == "menu"))
    async def handle_menu(callback: types.CallbackQuery) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        users = await asyncio.to_thread(deps.user_repo.list_pending_users)
        if not users:
            await respond(callback, "Нет ожидающих пользователей.")
            return
        _, kb = _build_user_list(users, 0)
        await respond(callback, "Ожидают подтверждения:", kb)

    @router.callback_query(UserCb.filter(F.action == "page"))
    async def handle_page(callback: types.CallbackQuery, callback_data: UserCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        users = await asyncio.to_thread(deps.user_repo.list_pending_users)
        if not users:
            await respond(callback, "Нет ожидающих пользователей.")
            return
        _, kb = _build_user_list(users, callback_data.page)
        await respond(callback, "Ожидают подтверждения:", kb)

    @router.callback_query(UserCb.filter(F.action == "open"))
    async def handle_open(callback: types.CallbackQuery, callback_data: UserCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        if not callback_data.user_id:
            await respond(callback, "Пользователь не найден.")
            return
        user = await asyncio.to_thread(deps.user_repo.get_by_id, callback_data.user_id)
        if not user:
            await respond(callback, "Пользователь не найден.")
            return
        text = (
            f"Пользователь: {user.first_name or ''} @{user.username or 'unknown'}\n"
            f"tg_id={user.telegram_user_id}\n"
            f"status={user.status} role={user.role}"
        )
        await respond(callback, text, _build_user_actions(callback_data.user_id))

    @router.callback_query(UserCb.filter(F.action == "approve"))
    async def handle_approve(callback: types.CallbackQuery, callback_data: UserCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        await asyncio.to_thread(deps.user_repo.set_status, callback_data.user_id, "active")
        await respond(callback, "Пользователь активирован.")

    @router.callback_query(UserCb.filter(F.action == "block"))
    async def handle_block(callback: types.CallbackQuery, callback_data: UserCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        await asyncio.to_thread(deps.user_repo.set_status, callback_data.user_id, "blocked")
        await respond(callback, "Пользователь заблокирован.")

    @router.callback_query(UserCb.filter(F.action.in_({"role_user", "role_power", "role_admin"})))
    async def handle_role(callback: types.CallbackQuery, callback_data: UserCb) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        role_map = {
            "role_user": "user",
            "role_power": "power",
            "role_admin": "admin",
        }
        role = role_map.get(callback_data.action)
        if not role:
            await respond(callback, "Некорректная роль.")
            return
        await asyncio.to_thread(deps.user_repo.set_role, callback_data.user_id, role)
        await respond(callback, f"Роль обновлена: {role}.")

    return router
