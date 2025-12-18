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

1. Поднимите PostgreSQL локально: `docker compose up -d`
2. Остановите при необходимости: `docker compose down`
3. Убедитесь, что в `.env` установлена строка `DATABASE_URL=postgresql+psycopg://pulsedidgest:pulsedidgest@localhost:5432/pulsedidgest`
4. Примените миграции: `alembic upgrade head`
5. Проверить таблицы: `docker compose exec postgres psql -U pulsedidgest -d pulsedidgest -c '\\dt'`

Collector использует `DATABASE_URL` во время запуска и сохраняет сообщения + решения Gemini через SQLAlchemy. Для просмотра доступных миграций используйте стандартные команды Alembic (`alembic history`, `alembic downgrade base`).

## Categories & Groups (MVP)

- Редактируйте `config/categories.yml`, задавая категории, промпты и список Telegram chat_id (BigInt) для каждой категории.
- Пример записи:

        categories:
          - name: default_jobs
            prompt: >
              Текст промпта на натуральном языке
            groups:
              - -1001234567890
            prefilter:
              min_length: 30
              include_any: ["job", "hiring"]
              exclude_any: ["crypto", "giveaway"]

- Collector синхронизирует таблицы `categories`, `source_groups`, `category_groups` при запуске.
- Проверить содержимое можно через psql: `docker compose exec postgres psql -U pulsedidgest -d pulsedidgest -c 'SELECT name FROM categories;'` и `... -c 'SELECT category_id, group_id FROM category_groups;'`.
- Prefilter (min_length/include/exclude) выполняется до LLM; пропущенные сообщения логируются как "Prefilter skipped".
- При ответе Gemini 429 (`RESOURCE_EXHAUSTED`) создаётся запись в `llm_errors`, включается cooldown и сообщения продолжают сохраняться без LLM-вызовов.

### Переменные окружения
- `TELEGRAM_API_ID` — API ID Telegram (integer)
- `TELEGRAM_API_HASH` — соответствующий API hash
- `TELEGRAM_SOURCE_CHAT` — username или ID источника
- `TELETHON_SESSION_NAME` — имя файла сессии (опционально, по умолчанию `pulsedidgest`)
- `GEMINI_API_KEY` — API-ключ Gemini (обязателен для фильтра)
- `GEMINI_MODEL` — имя модели Gemini (опционально, можно оставить пустым и использовать первую доступную `generateContent`)
- `GEMINI_COOLDOWN_SECONDS` — пауза после 429 RESOURCE_EXHAUSTED (по умолчанию 60 секунд)
- `DATABASE_URL` — строка подключения к PostgreSQL (например `postgresql+psycopg://user:password@localhost:5432/pulsedidgest`)
