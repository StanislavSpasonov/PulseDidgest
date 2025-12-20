# PulseDidgest — Tasks

## Backlog
- Digest delivery (hourly / daily)
- DeliveryPolicy per category
- Multi-user support
- Bot UI for managing categories and groups

## In Progress
- Уточнить задачу «upgrade»: что конкретно нужно обновить?

## Done
- Project initialization (clean architecture + docs) — структура репо и базовые спецификации
- Telegram collector: receive messages from one group — Telethon collector выводит новые сообщения в stdout
- Gemini filter (MVP) — сообщения проходят через Gemini и логируется решение pass/score/reason
- Database layer: persist messages and decisions — PostgreSQL + SQLAlchemy + Alembic
- Categories & Groups (MVP) — синхронизация категорий/групп, prefilter и логирование llm_errors
- Telegram Bot + Instant Delivery (MVP) — /start-регистрация и отправка pass=True решений пользователям
- Delivery Engine (instant + digest) — расписания hourly/interval/daily, cooldown и debug-уведомления
- Group management via Telethon — админ-бот управляет группами без forward
- Maintenance: reviewed project docs and set next task for group discovery
- Maintenance: merged feature/category-show-handler into dev

## Next
- Group discovery: add group by name via Telethon
