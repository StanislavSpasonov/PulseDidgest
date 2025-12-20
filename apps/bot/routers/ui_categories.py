from __future__ import annotations

import asyncio
from typing import Iterable, List, Optional, Set, Tuple

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apps.bot.ui.callbacks import CategoryCb, CategoryDeliveryCb, CategorySourceCb, LinkCb, NavCb, DeliveryCb
from apps.bot.ui.common import UiDeps, is_admin, respond, truncate
from apps.bot.ui.pagination import paginate, page_bounds


class CategoryCreateState(StatesGroup):
    name = State()
    prompt = State()
    sources_decision = State()
    sources_select = State()
    delivery_decision = State()
    delivery_custom_time = State()
    summary = State()


class CategoryEditState(StatesGroup):
    prompt = State()
    rename = State()


class CategorySearchState(StatesGroup):
    query = State()


def _nav_buttons(back_cb: str) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data=back_cb)
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(2)
    return builder.as_markup()


def _build_categories_menu() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Создать", callback_data=CategoryCb(action="create").pack())
    builder.button(text="📋 Список", callback_data=CategoryCb(action="list", page=0).pack())
    builder.button(text="🔍 Поиск", callback_data=CategoryCb(action="search").pack())
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(1)
    return builder.as_markup()


def _format_categories_list(
    categories, page: int, per_page: int, title: str
) -> Tuple[str, types.InlineKeyboardMarkup]:
    page_obj = paginate(categories, page, per_page)
    lines = [title]
    builder = InlineKeyboardBuilder()
    for category in page_obj.items:
        label = f"{category.name} ({'debug on' if category.debug_enabled else 'debug off'})"
        builder.button(
            text=label,
            callback_data=CategoryCb(action="detail", name=category.name).pack(),
        )
    if page_obj.total == 0:
        lines.append("Пока нет категорий.")
    if page_obj.total_pages > 1:
        prev_page, next_page = page_bounds(page_obj.page, page_obj.total_pages)
        row = []
        if page_obj.has_prev:
            row.append(
                types.InlineKeyboardButton(
                    text="⬅️ Prev",
                    callback_data=CategoryCb(action="list", page=prev_page).pack(),
                )
            )
        if page_obj.has_next:
            row.append(
                types.InlineKeyboardButton(
                    text="Next ➡️",
                    callback_data=CategoryCb(action="list", page=next_page).pack(),
                )
            )
        if row:
            builder.row(*row)
    builder.row(
        types.InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=CategoryCb(action="menu").pack(),
        ),
        types.InlineKeyboardButton(
            text="🏠 Домой",
            callback_data=NavCb(action="home").pack(),
        ),
    )
    return "\n".join(lines), builder.as_markup()


def _format_category_detail(category, links) -> Tuple[str, types.InlineKeyboardMarkup]:
    prompt_preview = truncate(category.prompt, 200) or "<empty>"
    lines = [
        f"Категория: {category.name}",
        f"Debug: {'on' if category.debug_enabled else 'off'}",
        f"Prompt: {prompt_preview}",
        "Источники:",
    ]
    if not links:
        lines.append("  (нет привязок)")
    else:
        for link, group in links:
            lines.append(
                f"- {group.title or group.tg_chat_id} "
                f"(chat_id={group.tg_chat_id}) mode={link.delivery_mode} "
                f"enabled={link.is_enabled}"
            )
    builder = InlineKeyboardBuilder()
    builder.button(text="🧾 Показать промпт", callback_data=CategoryCb(action="show_prompt", name=category.name).pack())
    builder.button(text="✏️ Изменить промпт", callback_data=CategoryCb(action="edit_prompt", name=category.name).pack())
    builder.button(text="✏️ Переименовать", callback_data=CategoryCb(action="rename", name=category.name).pack())
    toggle_text = "🧪 Debug OFF" if category.debug_enabled else "🧪 Debug ON"
    builder.button(text=toggle_text, callback_data=CategoryCb(action="toggle_debug", name=category.name).pack())
    builder.button(text="🔗 Источники", callback_data=LinkCb(action="category", category=category.name).pack())
    builder.button(text="🚚 Доставка", callback_data=DeliveryCb(action="category", category=category.name).pack())
    builder.button(text="🗑 Удалить", callback_data=CategoryCb(action="delete_confirm", name=category.name).pack())
    builder.button(text="⬅️ Назад", callback_data=CategoryCb(action="list", page=0).pack())
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(2)
    return "\n".join(lines), builder.as_markup()


def _build_sources_select_kb(
    groups, selected: Set[int], page: int, per_page: int
) -> Tuple[str, types.InlineKeyboardMarkup]:
    page_obj = paginate(groups, page, per_page)
    builder = InlineKeyboardBuilder()
    lines = ["Выберите источники (можно несколько):"]
    if not page_obj.items:
        lines.append("Нет зарегистрированных групп.")
    for group in page_obj.items:
        label = group.title or str(group.tg_chat_id)
        mark = "✅" if group.tg_chat_id in selected else "➕"
        builder.button(
            text=f"{mark} {label}",
            callback_data=CategorySourceCb(
                action="toggle", chat_id=int(group.tg_chat_id), page=page_obj.page
            ).pack(),
        )
    if page_obj.total_pages > 1:
        prev_page, next_page = page_bounds(page_obj.page, page_obj.total_pages)
        row = []
        if page_obj.has_prev:
            row.append(
                types.InlineKeyboardButton(
                    text="⬅️ Prev",
                    callback_data=CategorySourceCb(action="page", page=prev_page).pack(),
                )
            )
        if page_obj.has_next:
            row.append(
                types.InlineKeyboardButton(
                    text="Next ➡️",
                    callback_data=CategorySourceCb(action="page", page=next_page).pack(),
                )
            )
        if row:
            builder.row(*row)
    builder.row(
        types.InlineKeyboardButton(
            text="Дальше ➡️", callback_data=CategorySourceCb(action="done").pack()
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="⬅️ Назад", callback_data=CategoryCb(action="menu").pack()
        ),
        types.InlineKeyboardButton(
            text="🏠 Домой", callback_data=NavCb(action="home").pack()
        ),
    )
    return "\n".join(lines), builder.as_markup()


def _build_sources_decision_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Да, добавить",
        callback_data=CategoryCb(action="sources_yes").pack(),
    )
    builder.button(
        text="Пропустить",
        callback_data=CategoryCb(action="sources_skip").pack(),
    )
    builder.button(text="⬅️ Назад", callback_data=CategoryCb(action="menu").pack())
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(1)
    return builder.as_markup()


def _build_delivery_decision_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🚀 Instant",
        callback_data=CategoryDeliveryCb(action="select", mode="instant").pack(),
    )
    builder.button(
        text="🧾 Digest",
        callback_data=CategoryDeliveryCb(action="select", mode="digest").pack(),
    )
    builder.button(
        text="Пропустить",
        callback_data=CategoryDeliveryCb(action="select", mode="skip").pack(),
    )
    builder.button(
        text="⬅️ Назад", callback_data=CategoryCb(action="menu").pack()
    )
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(1)
    return builder.as_markup()


def _build_digest_presets_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="каждый час",
        callback_data=CategoryDeliveryCb(action="preset", mode="hourly").pack(),
    )
    builder.button(
        text="каждые 3 часа",
        callback_data=CategoryDeliveryCb(action="preset", mode="interval", value="180").pack(),
    )
    builder.button(
        text="ежедневно 08:00",
        callback_data=CategoryDeliveryCb(action="preset", mode="daily", value="08-00").pack(),
    )
    builder.button(
        text="ежедневно 18:00",
        callback_data=CategoryDeliveryCb(action="preset", mode="daily", value="18-00").pack(),
    )
    builder.button(
        text="своё время (HH:MM)",
        callback_data=CategoryDeliveryCb(action="custom_time").pack(),
    )
    builder.button(
        text="⬅️ Назад",
        callback_data=CategoryDeliveryCb(action="back").pack(),
    )
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(1)
    return builder.as_markup()


def _build_summary_kb() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Сохранить", callback_data=CategoryCb(action="create_save").pack())
    builder.button(text="⬅️ Назад", callback_data=CategoryDeliveryCb(action="back").pack())
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(1)
    return builder.as_markup()


def _format_delivery_summary(mode: Optional[str], interval: Optional[int], time_local: Optional[str]) -> str:
    if not mode or mode == "skip":
        return "Пропущено"
    if mode == "instant":
        return "Instant"
    if mode == "hourly":
        return "Digest: каждый час"
    if mode == "interval":
        return f"Digest: каждые {interval} минут"
    if mode == "daily":
        return f"Digest: ежедневно {time_local}"
    return mode


def build_router(deps: UiDeps) -> Router:
    router = Router()

    @router.callback_query(CategoryCb.filter(F.action == "menu"))
    async def handle_menu(callback: types.CallbackQuery) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        await respond(callback, "Категории", _build_categories_menu())

    @router.callback_query(CategoryCb.filter(F.action == "list"))
    async def handle_list(callback: types.CallbackQuery, callback_data: CategoryCb) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        categories = await asyncio.to_thread(deps.admin_repo.list_categories)
        text, kb = _format_categories_list(categories, callback_data.page, 6, "Категории:")
        await respond(callback, text, kb)

    @router.callback_query(CategoryCb.filter(F.action == "detail"))
    async def handle_detail(callback: types.CallbackQuery, callback_data: CategoryCb) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        try:
            category, links = await asyncio.to_thread(
                deps.admin_repo.get_category_details, callback_data.name
            )
        except Exception as exc:
            await respond(callback, f"Не удалось загрузить категорию: {exc}")
            return
        text, kb = _format_category_detail(category, links)
        await respond(callback, text, kb)

    @router.callback_query(CategoryCb.filter(F.action == "search"))
    async def handle_search(callback: types.CallbackQuery, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        await state.set_state(CategorySearchState.query)
        await respond(
            callback,
            "Введите часть названия категории для поиска:",
            _nav_buttons(CategoryCb(action="menu").pack()),
        )

    @router.message(CategorySearchState.query)
    async def handle_search_query(message: types.Message, state: FSMContext) -> None:
        if not is_admin(message.from_user.id if message.from_user else None, deps.admin_user_id):
            await message.answer("Меню доступно только администраторам.")
            await state.clear()
            return
        query = (message.text or "").strip().lower()
        if not query:
            await message.answer("Введите непустой запрос.")
            return
        categories = await asyncio.to_thread(deps.admin_repo.list_categories)
        filtered = [c for c in categories if query in c.name.lower()]
        if not filtered:
            await message.answer("Ничего не найдено.", reply_markup=_build_categories_menu())
            await state.clear()
            return
        text, kb = _format_categories_list(filtered, 0, 6, f"Найдено: {len(filtered)}")
        await message.answer(text, reply_markup=kb)
        await state.clear()

    @router.callback_query(CategoryCb.filter(F.action == "create"))
    async def handle_create(callback: types.CallbackQuery, state: FSMContext) -> None:
        if not is_admin(callback.from_user.id, deps.admin_user_id):
            await respond(callback, "Меню доступно только администраторам.")
            return
        await state.set_state(CategoryCreateState.name)
        await respond(
            callback,
            "Введите имя новой категории:",
            _nav_buttons(CategoryCb(action="menu").pack()),
        )

    @router.message(CategoryCreateState.name)
    async def handle_create_name(message: types.Message, state: FSMContext) -> None:
        if not is_admin(message.from_user.id if message.from_user else None, deps.admin_user_id):
            await message.answer("Меню доступно только администраторам.")
            await state.clear()
            return
        name = (message.text or "").strip()
        if not name:
            await message.answer("Имя категории не может быть пустым.")
            return
        await state.update_data(name=name)
        await state.set_state(CategoryCreateState.prompt)
        await message.answer(
            "Введите промпт для категории (можно несколько строк):",
            reply_markup=_nav_buttons(CategoryCb(action="menu").pack()),
        )

    @router.message(CategoryCreateState.prompt)
    async def handle_create_prompt(message: types.Message, state: FSMContext) -> None:
        if not is_admin(message.from_user.id if message.from_user else None, deps.admin_user_id):
            await message.answer("Меню доступно только администраторам.")
            await state.clear()
            return
        prompt = message.text or message.caption or ""
        await state.update_data(prompt=prompt)
        await state.set_state(CategoryCreateState.sources_decision)
        await message.answer(
            "Добавить источники сейчас?",
            reply_markup=_build_sources_decision_kb(),
        )

    @router.callback_query(CategoryCb.filter(F.action == "sources_yes"), CategoryCreateState.sources_decision)
    async def handle_sources_yes(callback: types.CallbackQuery, state: FSMContext) -> None:
        await state.set_state(CategoryCreateState.sources_select)
        groups = await asyncio.to_thread(deps.admin_repo.list_groups)
        await state.update_data(selected_chat_ids=[])
        text, kb = _build_sources_select_kb(groups, set(), 0, 6)
        await respond(callback, text, kb)

    @router.callback_query(CategoryCb.filter(F.action == "sources_skip"), CategoryCreateState.sources_decision)
    async def handle_sources_skip(callback: types.CallbackQuery, state: FSMContext) -> None:
        await state.update_data(selected_chat_ids=[])
        await state.set_state(CategoryCreateState.delivery_decision)
        await respond(callback, "Настроить доставку?", _build_delivery_decision_kb())

    @router.callback_query(CategorySourceCb.filter(F.action == "toggle"), CategoryCreateState.sources_select)
    async def handle_sources_toggle(
        callback: types.CallbackQuery, callback_data: CategorySourceCb, state: FSMContext
    ) -> None:
        data = await state.get_data()
        selected = set(data.get("selected_chat_ids", []))
        if callback_data.chat_id in selected:
            selected.remove(callback_data.chat_id)
        else:
            selected.add(callback_data.chat_id)
        await state.update_data(selected_chat_ids=list(selected))
        groups = await asyncio.to_thread(deps.admin_repo.list_groups)
        text, kb = _build_sources_select_kb(groups, selected, callback_data.page, 6)
        await respond(callback, text, kb)

    @router.callback_query(CategorySourceCb.filter(F.action == "page"), CategoryCreateState.sources_select)
    async def handle_sources_page(
        callback: types.CallbackQuery, callback_data: CategorySourceCb, state: FSMContext
    ) -> None:
        data = await state.get_data()
        selected = set(data.get("selected_chat_ids", []))
        groups = await asyncio.to_thread(deps.admin_repo.list_groups)
        text, kb = _build_sources_select_kb(groups, selected, callback_data.page, 6)
        await respond(callback, text, kb)

    @router.callback_query(CategorySourceCb.filter(F.action == "done"), CategoryCreateState.sources_select)
    async def handle_sources_done(callback: types.CallbackQuery, state: FSMContext) -> None:
        await state.set_state(CategoryCreateState.delivery_decision)
        await respond(callback, "Настроить доставку?", _build_delivery_decision_kb())

    @router.callback_query(CategoryDeliveryCb.filter(F.action == "select"), CategoryCreateState.delivery_decision)
    async def handle_delivery_select(
        callback: types.CallbackQuery, callback_data: CategoryDeliveryCb, state: FSMContext
    ) -> None:
        if callback_data.mode == "digest":
            await respond(callback, "Выберите расписание:", _build_digest_presets_kb())
            return
        await state.update_data(delivery_mode=callback_data.mode)
        await state.set_state(CategoryCreateState.summary)
        await _show_summary(callback, state)

    @router.callback_query(CategoryDeliveryCb.filter(F.action == "preset"), CategoryCreateState.delivery_decision)
    async def handle_delivery_preset(
        callback: types.CallbackQuery, callback_data: CategoryDeliveryCb, state: FSMContext
    ) -> None:
        mode = callback_data.mode
        interval = None
        time_local = None
        if mode == "interval":
            interval = int(callback_data.value or "0")
        if mode == "daily":
            time_local = (callback_data.value or "").replace("-", ":")
        await state.update_data(
            delivery_mode=mode, delivery_interval=interval, delivery_time=time_local
        )
        await state.set_state(CategoryCreateState.summary)
        await _show_summary(callback, state)

    @router.callback_query(CategoryDeliveryCb.filter(F.action == "custom_time"), CategoryCreateState.delivery_decision)
    async def handle_delivery_custom(callback: types.CallbackQuery, state: FSMContext) -> None:
        await state.set_state(CategoryCreateState.delivery_custom_time)
        await respond(
            callback,
            "Введите время в формате HH:MM:",
            _nav_buttons(CategoryCb(action="menu").pack()),
        )

    @router.message(CategoryCreateState.delivery_custom_time)
    async def handle_delivery_custom_time(message: types.Message, state: FSMContext) -> None:
        if not is_admin(message.from_user.id if message.from_user else None, deps.admin_user_id):
            await message.answer("Меню доступно только администраторам.")
            await state.clear()
            return
        value = (message.text or "").strip()
        if ":" not in value:
            await message.answer("Неверный формат. Пример: 08:00")
            return
        await state.update_data(delivery_mode="daily", delivery_time=value)
        await state.set_state(CategoryCreateState.summary)
        await _show_summary(message, state)

    @router.callback_query(CategoryDeliveryCb.filter(F.action == "back"))
    async def handle_delivery_back(callback: types.CallbackQuery, state: FSMContext) -> None:
        await state.set_state(CategoryCreateState.delivery_decision)
        await respond(callback, "Настроить доставку?", _build_delivery_decision_kb())

    async def _show_summary(
        event: types.CallbackQuery | types.Message, state: FSMContext
    ) -> None:
        data = await state.get_data()
        name = data.get("name")
        prompt = data.get("prompt") or ""
        selected = set(data.get("selected_chat_ids", []))
        mode = data.get("delivery_mode")
        interval = data.get("delivery_interval")
        time_local = data.get("delivery_time")
        lines = [
            "Проверьте настройки:",
            f"Имя: {name}",
            f"Промпт: {truncate(prompt, 200) or '<empty>'}",
            f"Источники: {len(selected)}",
            f"Доставка: {_format_delivery_summary(mode, interval, time_local)}",
        ]
        await respond(event, "\n".join(lines), _build_summary_kb())

    @router.callback_query(CategoryCb.filter(F.action == "create_save"), CategoryCreateState.summary)
    async def handle_create_save(callback: types.CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        name = data.get("name")
        prompt = data.get("prompt") or ""
        selected = set(data.get("selected_chat_ids", []))
        mode = data.get("delivery_mode")
        interval = data.get("delivery_interval")
        time_local = data.get("delivery_time")
        try:
            await asyncio.to_thread(deps.admin_repo.create_category, name)
            await asyncio.to_thread(deps.admin_repo.set_category_prompt, name, prompt)
            for chat_id in selected:
                await asyncio.to_thread(deps.admin_repo.bind_category, name, chat_id)
                if mode and mode not in {"skip"}:
                    await asyncio.to_thread(
                        deps.admin_repo.set_delivery,
                        name,
                        chat_id,
                        mode,
                        interval,
                        time_local,
                        deps.default_tz,
                    )
            deps.logger.info("Category created via UI: %s", name)
        except Exception as exc:
            await respond(callback, f"Не удалось создать категорию: {exc}")
            return
        await state.clear()
        await respond(callback, f"Категория '{name}' создана.", _build_categories_menu())

    @router.callback_query(CategoryCb.filter(F.action == "show_prompt"))
    async def handle_show_prompt(callback: types.CallbackQuery, callback_data: CategoryCb) -> None:
        try:
            category, _ = await asyncio.to_thread(
                deps.admin_repo.get_category_details, callback_data.name
            )
        except Exception as exc:
            await respond(callback, f"Не удалось загрузить категорию: {exc}")
            return
        text = category.prompt or "<empty>"
        builder = InlineKeyboardBuilder()
        builder.button(
            text="⬅️ Назад", callback_data=CategoryCb(action="detail", name=category.name).pack()
        )
        builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
        builder.adjust(2)
        await respond(callback, f"Промпт категории {category.name}:\n\n{text}", builder.as_markup())

    @router.callback_query(CategoryCb.filter(F.action == "edit_prompt"))
    async def handle_edit_prompt(callback: types.CallbackQuery, callback_data: CategoryCb, state: FSMContext) -> None:
        await state.set_state(CategoryEditState.prompt)
        await state.update_data(category=callback_data.name)
        await respond(
            callback,
            f"Введите новый промпт для '{callback_data.name}':",
            _nav_buttons(CategoryCb(action="detail", name=callback_data.name).pack()),
        )

    @router.message(CategoryEditState.prompt)
    async def handle_edit_prompt_message(message: types.Message, state: FSMContext) -> None:
        data = await state.get_data()
        name = data.get("category")
        if not name:
            await message.answer("Категория не выбрана.")
            await state.clear()
            return
        prompt = message.text or message.caption or ""
        try:
            await asyncio.to_thread(deps.admin_repo.set_category_prompt, name, prompt)
            deps.logger.info("Category prompt updated via UI: %s", name)
            await message.answer(f"Промпт обновлён для {name}")
        except Exception as exc:
            await message.answer(f"Не удалось обновить промпт: {exc}")
        await state.clear()

    @router.callback_query(CategoryCb.filter(F.action == "rename"))
    async def handle_rename(callback: types.CallbackQuery, callback_data: CategoryCb, state: FSMContext) -> None:
        await state.set_state(CategoryEditState.rename)
        await state.update_data(category=callback_data.name)
        await respond(
            callback,
            f"Введите новое имя для '{callback_data.name}':",
            _nav_buttons(CategoryCb(action="detail", name=callback_data.name).pack()),
        )

    @router.message(CategoryEditState.rename)
    async def handle_rename_message(message: types.Message, state: FSMContext) -> None:
        data = await state.get_data()
        name = data.get("category")
        new_name = (message.text or "").strip()
        if not name:
            await message.answer("Категория не выбрана.")
            await state.clear()
            return
        if not new_name:
            await message.answer("Имя не может быть пустым.")
            return
        try:
            await asyncio.to_thread(deps.admin_repo.rename_category, name, new_name)
            deps.logger.info("Category renamed via UI: %s -> %s", name, new_name)
            await message.answer(f"Категория переименована: {new_name}")
        except Exception as exc:
            await message.answer(f"Не удалось переименовать: {exc}")
        await state.clear()

    @router.callback_query(CategoryCb.filter(F.action == "toggle_debug"))
    async def handle_toggle_debug(callback: types.CallbackQuery, callback_data: CategoryCb) -> None:
        try:
            category, _ = await asyncio.to_thread(
                deps.admin_repo.get_category_details, callback_data.name
            )
            new_value = not category.debug_enabled
            await asyncio.to_thread(deps.admin_repo.set_category_debug, category.name, new_value)
            deps.logger.info("Category debug toggled via UI: %s -> %s", category.name, new_value)
            await respond(
                callback,
                f"Debug {'включён' if new_value else 'выключен'} для {category.name}.",
                _build_categories_menu(),
            )
        except Exception as exc:
            await respond(callback, f"Не удалось изменить debug: {exc}")

    @router.callback_query(CategoryCb.filter(F.action == "delete_confirm"))
    async def handle_delete_confirm(callback: types.CallbackQuery, callback_data: CategoryCb) -> None:
        builder = InlineKeyboardBuilder()
        builder.button(
            text="Да, удалить",
            callback_data=CategoryCb(action="delete_yes", name=callback_data.name).pack(),
        )
        builder.button(
            text="Отмена",
            callback_data=CategoryCb(action="detail", name=callback_data.name).pack(),
        )
        builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
        builder.adjust(1)
        await respond(callback, f"Удалить категорию '{callback_data.name}'?", builder.as_markup())

    @router.callback_query(CategoryCb.filter(F.action == "delete_yes"))
    async def handle_delete_yes(callback: types.CallbackQuery, callback_data: CategoryCb) -> None:
        try:
            await asyncio.to_thread(deps.admin_repo.delete_category, callback_data.name)
            deps.logger.info("Category deleted via UI: %s", callback_data.name)
            await respond(callback, f"Категория '{callback_data.name}' удалена.", _build_categories_menu())
        except Exception as exc:
            await respond(callback, f"Не удалось удалить: {exc}")

    return router
