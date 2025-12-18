# PulseDidgest — Tasks

## Backlog
- Digest delivery (hourly / daily)
- DeliveryPolicy per category
- Multi-user support
- Bot UI for managing categories and groups

## In Progress
- (пусто)

## Done
- Project initialization (clean architecture + docs) — структура репо и базовые спецификации
- Telegram collector: receive messages from one group — Telethon collector выводит новые сообщения в stdout
- Gemini filter (MVP) — сообщения проходят через Gemini и логируется решение pass/score/reason
- Database layer: persist messages and decisions — PostgreSQL + SQLAlchemy + Alembic

## Next
- Categories & Groups: prompts and group mapping
