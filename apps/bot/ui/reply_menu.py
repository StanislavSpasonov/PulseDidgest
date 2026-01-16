from __future__ import annotations

from aiogram import types


def build_menu_button_keyboard() -> types.ReplyKeyboardMarkup:
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="☰ Меню")]],
        resize_keyboard=True,
    )
