# PulseDidgest — Project Memo

## Архитектура
Используется Clean Architecture:
- Domain — бизнес-сущности и правила
- Application — use cases
- Infrastructure — Telegram, Gemini, БД
- Interface — форматирование и доставка сообщений
- Для collector выбран Telethon
- Доставка digest работает через outbox + scheduler (без прямой отправки из LLM pipeline)

## Почему так
- Минимальная связанность
- Возможность расширять функциональность
- Удобный контроль задач при работе с Codex

## Принцип разработки
Сначала вертикальный MVP.
Любое усложнение — только после работающего сценария.

## Bot UI
Админский интерфейс доступен по /start, /menu или кнопке “☰ Меню” снизу — всё управление через кнопки (категории, группы, привязки, доставка, отчёты).

## Quality Sweep
Quality sweep выполнен. Тесты запускаются командой: `python -m pytest -q`.
Добавлены unit-тесты для ключевых use cases (prefilter, delivery, telethon discovery).
