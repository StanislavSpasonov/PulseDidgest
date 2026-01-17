# PulseDidgest — Tasks

## Backlog
- Multi-user support

## In Progress
- Epic: Multi-user (RBAC/ACL + персональная доставка + feedback/inbox)

## Done
- Fix: UI edit игнорирует ошибку "message is not modified" от Telegram
- Audit: зафиксированы текущие таблицы, команды бота, admin gate и user_id (см. PROJECT_MEMO.md)
- Users: добавлены role/status + /start gating + bootstrap admin
- ACL: owner_user_id + category_acl + UI выдачи/отзыва доступа
- Delivery: персональные настройки + персонифицированная доставка через outbox
- Feedback/Inbox: заявки и обратная связь + inbox для admin
- Tests: ACL resolve, user delivery policy, status gating
- Fix: UI Access callback data укорочены (stateful category_id)
- Fix: ACL grant/revoke callbacks укорочены (stateful user_id)
- Fix: UI пользователей позволяет перейти к списку всех и менять роли активных
- Tests: контроль длины callback data (64 bytes) для основных UI callbacks
- Fix: тест callback length учитывает реальные комбинации callback data
- UI: доставка для пользователя расширена до полноценной настройки (instant/digest/presets/custom)
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
- Launcher: skip collector when TELEGRAM_SOURCE_CHAT is missing
- Collector: dynamic routing from DB (snapshot cache + message routing)
- Fix: user repository active users for instant delivery
- Delivery: links + HTML formatting for instant/digest
- Fix: separate Telethon sessions for bot/collector to avoid SQLite lock
- Env: set COLLECTOR_TELETHON_SESSION_NAME in .env
- UI: persistent reply keyboard with ☰ Меню button
- Epic: MVP hardening (dynamic routing, delivery outbox/scheduler, formatting, UX, tests, docs)

## Next
- Проверить авторизацию Telethon сессии на сервере (collector auth)
