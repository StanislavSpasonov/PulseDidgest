# PulseDidgest

Telegram → LLM → Signal → Delivery

Early-stage MVP.

## Telegram Collector (MVP)

1. Скопируйте `.env.example` в `.env` и заполните переменные окружения.
2. Установите зависимости: `pip install -r requirements.txt`.
3. Запустите collector командой `python apps/collector/main.py`.

Collector автоматически загружает `.env` из корня проекта (python-dotenv), берёт `TELETHON_SESSION_NAME` из env (или использует `pulsedidgest` по умолчанию), логирует каждое новое сообщение и отправляет текст в Gemini для классификации. В логах видно, какую модель использует LLM, и решение сохраняется в PostgreSQL.

## Gemini Filter (MVP)

Для фильтрации используется Gemini (Google Generative AI). Collector передаёт текст сообщения и получает строго JSON-ответ вида `{ "pass": bool, "score": 0..1, "reason": "..." }`. Решение выводится в stdout и сохраняется в PostgreSQL.

Чтобы узнать доступные модели и выбрать подходящую, используйте хелпер:

```
python apps/tools/list_gemini_models.py
```

Скрипт выведет модели и отметит первую, которая поддерживает `generateContent`. Эту модель можно записать в `GEMINI_MODEL`.

## Persistence (PostgreSQL MVP)

1. Создайте БД PostgreSQL (пример): `createdb pulsedidgest`
2. Обновите `DATABASE_URL` в `.env` (формат `postgresql+psycopg://user:password@host:port/db`)
3. Примените миграции: `alembic upgrade head`

Collector использует `DATABASE_URL` во время запуска и сохраняет сообщения + решения Gemini через SQLAlchemy. Для просмотра доступных миграций используйте стандартные команды Alembic (`alembic history`, `alembic downgrade base`).

### Переменные окружения
- `TELEGRAM_API_ID` — API ID Telegram (integer)
- `TELEGRAM_API_HASH` — соответствующий API hash
- `TELEGRAM_SOURCE_CHAT` — username или ID источника
- `TELETHON_SESSION_NAME` — имя файла сессии (опционально, по умолчанию `pulsedidgest`)
- `GEMINI_API_KEY` — API-ключ Gemini (обязателен для фильтра)
- `GEMINI_MODEL` — имя модели Gemini (опционально, можно оставить пустым и использовать первую доступную `generateContent`)
- `DATABASE_URL` — строка подключения к PostgreSQL (например `postgresql+psycopg://user:password@localhost:5432/pulsedidgest`)
