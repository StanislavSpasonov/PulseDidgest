# PulseDidgest — Tasks

## Backlog
- Digest delivery (hourly / daily)
- DeliveryPolicy per category
- Multi-user support

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
- Bot UI v1 (inline keyboard + wizard) — /start и /menu ведут в UI, категории/группы/привязки/доставка/отчёты/настройки
- Fix: digest preset callback values without ':' to avoid aiogram errors
- Fix: category callbacks use IDs to avoid 64-byte limit
- Quality sweep: cleanup, config refactor, tests, docs
- Test coverage: added unit tests for delivery/prefilter/telethon/group management
- Fix: bot startup sys.path initialization before src imports
- UI: one-column list keyboards + truncation helper
- Fix: link selection callbacks shortened + navigation state cleared
- Tests: navigation layout (list keyboard back/home ordering)
- Logging: collector pipeline diagnostics (bindings/persist/decisions)
- Launcher: single entrypoint runs bot + collector

## Next
- QA: проверить unified launcher + Bot UI по acceptance criteria
