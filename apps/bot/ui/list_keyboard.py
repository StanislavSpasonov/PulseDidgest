from __future__ import annotations

from typing import Callable, Iterable, List, Sequence, Tuple, TypeVar

from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apps.bot.ui.pagination import Page, page_bounds, paginate

T = TypeVar("T")

LIST_BUTTON_MAX_LEN = 52


def truncate(text: str, max_len: int = LIST_BUTTON_MAX_LEN) -> str:
    if max_len <= 0:
        return ""
    value = (text or "").strip()
    if len(value) <= max_len:
        return value
    if max_len == 1:
        return "…"
    return value[: max_len - 1] + "…"


def build_one_column_list(
    items: Sequence[T],
    label_fn: Callable[[T], str],
    callback_fn: Callable[[T], str],
    page: int,
    page_size: int,
    show_prev_next: bool = True,
    show_back_home: bool = True,
    page_callback_fn: Callable[[int], str] | None = None,
    back_cb: str | None = None,
    home_cb: str | None = None,
    extra_rows: List[List[types.InlineKeyboardButton]] | None = None,
) -> Tuple[Page[T], types.InlineKeyboardMarkup]:
    page_obj = paginate(items, page, page_size)
    builder = InlineKeyboardBuilder()

    for item in page_obj.items:
        label = truncate(label_fn(item))
        builder.row(
            types.InlineKeyboardButton(
                text=label, callback_data=callback_fn(item)
            )
        )

    if show_prev_next and page_obj.total_pages > 1 and page_callback_fn:
        prev_page, next_page = page_bounds(page_obj.page, page_obj.total_pages)
        row: List[types.InlineKeyboardButton] = []
        if page_obj.has_prev:
            row.append(
                types.InlineKeyboardButton(
                    text="⬅️ Prev",
                    callback_data=page_callback_fn(prev_page),
                )
            )
        if page_obj.has_next:
            row.append(
                types.InlineKeyboardButton(
                    text="Next ➡️",
                    callback_data=page_callback_fn(next_page),
                )
            )
        if row:
            builder.row(*row)

    if extra_rows:
        for row in extra_rows:
            builder.row(*row)

    if show_back_home and (back_cb or home_cb):
        row: List[types.InlineKeyboardButton] = []
        if back_cb:
            row.append(
                types.InlineKeyboardButton(
                    text="⬅️ Назад", callback_data=back_cb
                )
            )
        if home_cb:
            row.append(
                types.InlineKeyboardButton(
                    text="🏠 Домой", callback_data=home_cb
                )
            )
        if row:
            builder.row(*row)

    return page_obj, builder.as_markup()
