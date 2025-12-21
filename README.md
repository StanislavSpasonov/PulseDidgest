# PulseDidgest

Telegram → LLM → Signal → Delivery

Early-stage MVP.

## Telegram Collector (MVP)

1. Скопируйте `.env.example` в `.env` и заполните переменные окружения.
2. Установите зависимости: `pip install -r requirements.txt`.
3. Запустите collector командой `python -m apps.collector.main` (или `python -m apps.main`, чтобы поднять bot + collector вместе).

Collector автоматически загружает `.env` из корня проекта (python-dotenv), берёт `TELETHON_SESSION_NAME` из env (или использует `pulsedidgest` по умолчанию), логирует каждое новое сообщение и отправляет текст в Gemini для классификации. Маршрутизация берётся из БД и обновляется каждые `COLLECTOR_REFRESH_SECONDS` (по умолчанию 30 сек). В логах видно, какую модель использует LLM, и решение сохраняется в PostgreSQL.

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

- Категории и источники теперь живут в БД (бот управляет привязками). `config/categories.yml` используется только для начального сидирования, если `CONFIG_SYNC_MODE=seed_if_empty`.
- Расширенный пример:

        categories:
          - name: default_jobs
            prompt: >
              Текст промпта на натуральном языке
            debug_enabled: false
            prefilter:
              min_length: 30
              include_any: ["job", "hiring"]
              exclude_any: ["crypto", "giveaway"]
            groups:
              - chat_id: -1001234567890
                title: Berlin Jobs
                delivery:
                  mode: instant
                  is_enabled: true
              - chat_id: -1009876543210
                title: Remote Only
                delivery:
                  mode: interval
                  minutes: 60
                  timezone: Europe/Berlin
                  is_enabled: true

- Collector может сидировать таблицы `categories`, `source_groups`, `category_groups` при запуске (если включён `CONFIG_SYNC_MODE`).
- Проверить содержимое можно через psql: `docker compose exec postgres psql -U pulsedidgest -d pulsedidgest -c 'SELECT name FROM categories;'` и `... -c 'SELECT category_id, group_id FROM category_groups;'`.
- Prefilter (min_length/include/exclude) выполняется до LLM; пропущенные сообщения логируются как "Prefilter skipped".
- При ответе Gemini 429 (`RESOURCE_EXHAUSTED`) создаётся запись в `llm_errors`, включается cooldown и сообщения продолжают сохраняться без LLM-вызовов.

## Delivery Engine (Instant + Digest)

- Instant-доставка работает для привязок с `delivery.mode=instant`: pass=True решения улетают сразу после обработки Gemini.
- Digest-engine запускается внутри collector (tick задаётся `DELIVERY_TICK_SECONDS`, по умолчанию 60s) и проверяет привязки с режимами `hourly`, `interval <minutes>`, `daily <HH:MM> [TZ]`.
- В delivery сообщениях добавляются кликабельные ссылки на исходные посты и список URL из текста; длинные тексты идут как preview + ссылка на источник.
- Для `interval` требуется `minutes>0`, для `daily` — локальное время `HH:MM` и таймзона (по умолчанию `DEFAULT_TZ`).
- Digest состоит из заголовка `[category + group]` и списка последних непродоставленных pass-решений (score, reason, урезанный текст). После успешной отправки решения помечаются `delivered_at=NOW()` и `category_groups.last_sent_at` обновляется.
- Debug режим (`debug_enabled: true`) шлёт админу (см. `TELEGRAM_ADMIN_USER_ID`) подробности по каждому решению, но не больше 20 событий в минуту на категорию.

## Telegram Bot + Instant Delivery (MVP)

1. Создайте бота через BotFather и положите токен в `.env` (`TELEGRAM_BOT_TOKEN`).
2. Запустите бота: `python apps/bot/main.py` и выполните `/start` из Telegram (бот ответит `Registered. chat_id=...`).
3. Запустите collector (`python -m apps.collector.main`) или оба процесса сразу (`python -m apps.main`). Когда Gemini вернёт `pass=true`, решение будет немедленно отправлено всем активным пользователям. В сообщении отображается категория, score и исходный текст.
4. Проверить доставку можно в БД: `docker compose exec postgres psql -U pulsedidgest -d pulsedidgest -c 'SELECT delivered_at FROM decisions ORDER BY created_at DESC LIMIT 5;'`.
5. Навигация: внизу всегда доступна кнопка “☰ Меню” (reply keyboard), она открывает главное меню.

## Managing Telegram Groups

Используйте Telethon user session:
- `/groups_my` — показать все группы/каналы текущего пользователя.
- `/group_add_name <имя или username>` — найти чат по названию/username и добавить его в систему без forward.
- `/group_add_chat <chat_id> [title]` — ручное добавление, если известен chat_id.

Если бот не находит чат, сначала вызовите `/groups_my` и скопируйте нужное название/username.

### Переменные окружения
- `TELEGRAM_API_ID` — API ID Telegram (integer)
- `TELEGRAM_API_HASH` — соответствующий API hash
- `TELEGRAM_SOURCE_CHAT` — optional legacy override (single source chat for dev)
- `TELETHON_SESSION_NAME` — имя файла сессии (опционально, по умолчанию `pulsedidgest`)
- `COLLECTOR_TELETHON_SESSION_NAME` — отдельная сессия для collector (рекомендуется, чтобы избежать SQLite lock)
- `TELEGRAM_BOT_TOKEN` — токен бота для /start и instant-доставки
- `TELEGRAM_ADMIN_USER_ID` — ID администратора (для debug/бот-команд)
- `GEMINI_API_KEY` — API-ключ Gemini (обязателен для фильтра)
- `GEMINI_MODEL` — имя модели Gemini (опционально, можно оставить пустым и использовать первую доступную `generateContent`)
- `GEMINI_COOLDOWN_SECONDS` — пауза после 429 RESOURCE_EXHAUSTED (по умолчанию 60 секунд)
- `DEFAULT_TZ` — таймзона по умолчанию (используется в delivery/daily)
- `CONFIG_SYNC_MODE` — `seed_if_empty` (по умолчанию) или `off`
- `DELIVERY_TICK_SECONDS` — частота проверки digest-расписаний (по умолчанию 60 секунд)
- `COLLECTOR_REFRESH_SECONDS` — частота обновления маршрутизации из БД (по умолчанию 30 секунд)
- `DATABASE_URL` — строка подключения к PostgreSQL (например `postgresql+psycopg://user:password@localhost:5432/pulsedidgest`)

## Dev: setup + run + tests

1. Создать виртуальное окружение: `python -m venv .venv`
2. Активировать его: `source .venv/bin/activate`
3. Установить зависимости: `pip install -r requirements.txt`
4. Подготовить env: `cp .env.example .env` и заполнить значения
5. Запуск:
   - collector: `python -m apps.collector.main`
   - bot: `python -m apps.bot.main`
   - вместе: `python -m apps.main`
6. Тесты: `python -m pytest -q`
