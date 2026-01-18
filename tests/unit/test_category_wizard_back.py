from __future__ import annotations

from apps.bot.routers import ui_categories


def test_create_wizard_back_from_prompt_to_name() -> None:
    prev = ui_categories._resolve_create_back_state(
        ui_categories.CategoryCreateState.prompt.state,
        {"name": "Работа"},
    )
    assert prev == ui_categories.CategoryCreateState.name.state


def test_create_wizard_back_from_delivery_decision_to_sources_select() -> None:
    prev = ui_categories._resolve_create_back_state(
        ui_categories.CategoryCreateState.delivery_decision.state,
        {"sources_flow": "select"},
    )
    assert prev == ui_categories.CategoryCreateState.sources_select.state


def test_create_wizard_back_from_delivery_decision_to_sources_decision() -> None:
    prev = ui_categories._resolve_create_back_state(
        ui_categories.CategoryCreateState.delivery_decision.state,
        {"sources_flow": "skip"},
    )
    assert prev == ui_categories.CategoryCreateState.sources_decision.state


def test_create_wizard_back_from_first_step_exits() -> None:
    prev = ui_categories._resolve_create_back_state(
        ui_categories.CategoryCreateState.name.state,
        {},
    )
    assert prev is None


def test_create_wizard_prefill_name_prompt() -> None:
    text = ui_categories._format_create_name_text("Berlin Jobs")
    assert "Текущее имя" in text
    assert "Berlin Jobs" in text


def test_create_wizard_prefill_prompt_text() -> None:
    text = ui_categories._format_create_prompt_text("Тестовый промпт")
    assert "Текущий текст" in text
    assert "Тестовый промпт" in text
