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

## Audit: multi-user baseline
- Таблицы в БД: messages, decisions, categories, source_groups, category_groups, llm_errors, users, delivery_outbox.
- users: tg_user_id, chat_id, username, is_active, created_at (без role/status).
- Категории и источники глобальные; бинд (category_groups) содержит delivery_mode/interval/time/tz/is_enabled.
- Delivery: instant/digest, outbox + scheduler; default delivery на уровне categories, override на уровне category_groups.
- Bot UI: /start регистрирует пользователя как active, меню и все экраны админские; reply кнопка "☰ Меню".
- Команды: /start, /menu, /hide_menu, /groups_my, /group_add_name, /group_add_chat, /delivery_errors.
- Admin gate: is_admin сверяет user_id с TELEGRAM_ADMIN_USER_ID из env (точечные проверки в routers/main).
