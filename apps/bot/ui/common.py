from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Iterable, Optional

from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from src.application.use_cases.manage_groups_telethon import (
    AddGroupByNameUseCase,
    ListUserChatsUseCase,
    SearchUserChatsUseCase,
)
from src.domain.entities import UserRecord
from src.infrastructure.db.repositories import (
    SQLAlchemyAdminRepository,
    SQLAlchemyCategoryAccessRepository,
    SQLAlchemyDeliveryRepository,
    SQLAlchemyFeedbackRepository,
    SQLAlchemyUserDeliveryRepository,
    SQLAlchemyUserRepository,
)


@dataclass
class UiDeps:
    admin_user_id: int
    default_tz: str
    admin_repo: SQLAlchemyAdminRepository
    access_repo: SQLAlchemyCategoryAccessRepository
    user_repo: SQLAlchemyUserRepository
    delivery_repo: SQLAlchemyDeliveryRepository
    user_delivery_repo: SQLAlchemyUserDeliveryRepository
    feedback_repo: SQLAlchemyFeedbackRepository
    list_chats_use_case: ListUserChatsUseCase
    search_chats_use_case: SearchUserChatsUseCase
    add_group_use_case: AddGroupByNameUseCase
    telethon_dialog_limit: int
    settings_snapshot: dict[str, str]
    logger: logging.Logger


async def fetch_user(
    deps: UiDeps,
    telegram_user_id: int | None,
) -> UserRecord | None:
    if not telegram_user_id:
        return None
    return await asyncio.to_thread(
        deps.user_repo.get_by_telegram_id,
        telegram_user_id,
    )


def is_admin(user: UserRecord | None, admin_user_id: int) -> bool:
    if not user or user.status != "active":
        return False
    if user.role == "admin":
        return True
    return bool(admin_user_id and user.telegram_user_id == admin_user_id)


def is_power(user: UserRecord | None, admin_user_id: int) -> bool:
    if not user or user.status != "active":
        return False
    return user.role in {"power", "admin"} or bool(
        admin_user_id and user.telegram_user_id == admin_user_id
    )


def is_active(user: UserRecord | None) -> bool:
    return bool(user and user.status == "active")


def is_pending(user: UserRecord | None) -> bool:
    return bool(user and user.status == "pending")


def is_blocked(user: UserRecord | None) -> bool:
    return bool(user and user.status == "blocked")


def format_chat_line(chat) -> str:
    username = f" (@{chat.username})" if chat.username else ""
    label = chat.title or (f"@{chat.username}" if chat.username else str(chat.chat_id))
    return f"{label}{username} — {chat.chat_id} [{chat.chat_type}]"


def truncate(text: str, limit: int = 200) -> str:
    stripped = (text or "").strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[:limit] + "…"


async def respond(
    event: types.CallbackQuery | types.Message,
    text: str,
    reply_markup: Optional[types.InlineKeyboardMarkup] = None,
) -> None:
    if isinstance(event, types.CallbackQuery):
        if event.message:
            await safe_edit_text(event.message, text, reply_markup=reply_markup)
        await event.answer()
    else:
        await event.answer(text, reply_markup=reply_markup)


def _normalize_markup(markup: Optional[types.InlineKeyboardMarkup]) -> Optional[dict]:
    if markup is None:
        return None
    if hasattr(markup, "model_dump"):
        return markup.model_dump(exclude_none=True)
    if hasattr(markup, "to_python"):
        return markup.to_python()
    return {"value": markup}


def _is_same_content(
    message: types.Message, text: str, reply_markup: Optional[types.InlineKeyboardMarkup]
) -> bool:
    current_text = message.text or ""
    if current_text != (text or ""):
        return False
    return _normalize_markup(message.reply_markup) == _normalize_markup(reply_markup)


async def safe_edit_text(
    message: types.Message,
    text: str,
    reply_markup: Optional[types.InlineKeyboardMarkup] = None,
) -> None:
    if _is_same_content(message, text, reply_markup):
        return
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


def build_text_list(lines: Iterable[str], empty_text: str) -> str:
    output = [line for line in lines if line]
    return "\n".join(output) if output else empty_text
