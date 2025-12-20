from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Optional

from aiogram import types
from src.application.use_cases.manage_groups_telethon import (
    AddGroupByNameUseCase,
    ListUserChatsUseCase,
    SearchUserChatsUseCase,
)
from src.infrastructure.db.repositories import (
    SQLAlchemyAdminRepository,
    SQLAlchemyDeliveryRepository,
    SQLAlchemyUserRepository,
)


@dataclass
class UiDeps:
    admin_user_id: int
    default_tz: str
    admin_repo: SQLAlchemyAdminRepository
    user_repo: SQLAlchemyUserRepository
    delivery_repo: SQLAlchemyDeliveryRepository
    list_chats_use_case: ListUserChatsUseCase
    search_chats_use_case: SearchUserChatsUseCase
    add_group_use_case: AddGroupByNameUseCase
    telethon_dialog_limit: int
    settings_snapshot: dict[str, str]
    logger: logging.Logger


def is_admin(user_id: Optional[int], admin_user_id: int) -> bool:
    return bool(user_id and admin_user_id and user_id == admin_user_id)


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
            await event.message.edit_text(text, reply_markup=reply_markup)
        await event.answer()
    else:
        await event.answer(text, reply_markup=reply_markup)


def build_text_list(lines: Iterable[str], empty_text: str) -> str:
    output = [line for line in lines if line]
    return "\n".join(output) if output else empty_text
