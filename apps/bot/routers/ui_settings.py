from __future__ import annotations

from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apps.bot.ui.callbacks import NavCb, SettingsCb
from apps.bot.ui.common import UiDeps, fetch_user, is_admin, respond


def _build_settings_text(settings: dict[str, str]) -> str:
    lines = ["Настройки:"]
    for key, value in settings.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def _build_settings_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    return builder.as_markup()


def build_router(deps: UiDeps) -> Router:
    router = Router()

    async def _is_admin(user_id: int | None) -> bool:
        user = await fetch_user(deps, user_id)
        return is_admin(user, deps.admin_user_id)

    @router.callback_query(SettingsCb.filter(F.action == "menu"))
    async def handle_menu(callback: types.CallbackQuery) -> None:
        if not await _is_admin(callback.from_user.id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        text = _build_settings_text(deps.settings_snapshot)
        await respond(callback, text, _build_settings_kb())

    return router
