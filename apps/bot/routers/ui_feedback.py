from __future__ import annotations

import asyncio

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apps.bot.ui.callbacks import FeedbackCb, NavCb
from apps.bot.ui.common import UiDeps, fetch_user, respond
from src.domain.entities import FeedbackMessageRecord


class FeedbackStates(StatesGroup):
    waiting_for_text = State()


def _build_feedback_menu() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💬 Отзыв", callback_data=FeedbackCb(action="feedback").pack())
    builder.button(text="🧩 Идея для промпта", callback_data=FeedbackCb(action="suggest_prompt").pack())
    builder.button(text="➕ Предложить источник", callback_data=FeedbackCb(action="suggest_source").pack())
    builder.button(text="🏠 Домой", callback_data=NavCb(action="home").pack())
    builder.adjust(1)
    return builder.as_markup()


def build_router(deps: UiDeps) -> Router:
    router = Router()

    @router.callback_query(FeedbackCb.filter(F.action == "menu"))
    async def handle_menu(callback: types.CallbackQuery) -> None:
        await respond(callback, "Обратная связь", _build_feedback_menu())

    @router.callback_query(FeedbackCb.filter(F.action == "request_access"))
    async def handle_request_access(callback: types.CallbackQuery) -> None:
        user = await fetch_user(deps, callback.from_user.id)
        if not user:
            await respond(callback, "Сначала выполните /start.")
            return
        text = f"Access request from @{user.username or 'unknown'} (tg_id={user.telegram_user_id})"
        record = FeedbackMessageRecord(
            id=None,
            user_id=user.id,
            type="access_request",
            text=text,
            status="new",
        )
        await asyncio.to_thread(deps.feedback_repo.create, record)
        await respond(callback, "Запрос доступа отправлен админу.")

    @router.callback_query(FeedbackCb.filter(F.action.in_({"feedback", "suggest_prompt", "suggest_source"})))
    async def handle_feedback_type(callback: types.CallbackQuery, state: FSMContext) -> None:
        await state.set_state(FeedbackStates.waiting_for_text)
        await state.update_data(feedback_type=callback.data)
        await respond(callback, "Напишите сообщение и отправьте его одним текстом.")

    @router.message(FeedbackStates.waiting_for_text)
    async def handle_feedback_text(message: types.Message, state: FSMContext) -> None:
        if not message.from_user:
            await message.answer("Нет данных пользователя.")
            return
        data = await state.get_data()
        raw_action = data.get("feedback_type")
        feedback_type = "feedback"
        if raw_action:
            try:
                feedback_type = FeedbackCb.unpack(raw_action).action
            except Exception:
                feedback_type = "feedback"
        user = await fetch_user(deps, message.from_user.id)
        if not user:
            await message.answer("Сначала выполните /start.")
            await state.clear()
            return
        record = FeedbackMessageRecord(
            id=None,
            user_id=user.id,
            type=feedback_type,
            text=message.text or "",
            status="new",
        )
        await asyncio.to_thread(deps.feedback_repo.create, record)
        await message.answer("Спасибо! Сообщение отправлено админу.")
        await state.clear()

    return router
