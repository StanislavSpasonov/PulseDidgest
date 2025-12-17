# PulseDidgest — Project Memo

## Архитектура
Используется Clean Architecture:
- Domain — бизнес-сущности и правила
- Application — use cases
- Infrastructure — Telegram, Gemini, БД
- Interface — форматирование и доставка сообщений
- Для collector выбран Telethon

## Почему так
- Минимальная связанность
- Возможность расширять функциональность
- Удобный контроль задач при работе с Codex

## Принцип разработки
Сначала вертикальный MVP.
Любое усложнение — только после работающего сценария.
