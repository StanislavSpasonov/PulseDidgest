# PulseDidgest

Telegram → LLM → Signal → Delivery

Early-stage MVP.

## Telegram Collector (MVP)

1. Скопируйте `.env.example` в `.env` и заполните переменные окружения.
2. Установите зависимости: `pip install -r requirements.txt`.
3. Запустите collector командой `python -m apps.collector.main` (или `python -m apps.main`, чтобы поднять bot + collector вместе).

Collector автоматически загружает `.env` из корня проекта (python-dotenv), берёт путь `TELETHON_SESSION` (или `TELETHON_SESSION_NAME` по умолчанию), логирует каждое новое сообщение и отправляет текст в Gemini для классификации. Маршрутизация берётся из БД и обновляется каждые `COLLECTOR_REFRESH_SECONDS` (по умолчанию 30 сек). В логах видно, какую модель использует LLM, и решение сохраняется в PostgreSQL.

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

- Delivery policy задаётся на уровне привязки (category↔chat): `enabled` + `mode` (`instant` или `digest`) + расписание (`hourly`/`interval`/`daily`).
- Instant-доставка: pass=True решения отправляются сразу.
- Digest-доставка: pass=True решения складываются в outbox и отправляются по расписанию (scheduler работает внутри collector, tick задаётся `DELIVERY_TICK_SECONDS`).
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
6. Ошибки доставки: `/delivery_errors [limit]`.

## Multi-user: roles, access, delivery, feedback

- Роли: `user` (просмотр и доставка), `power` (создание/редактирование своих категорий, источники/привязки), `admin` (полный доступ).
- Статусы: `pending` (ожидает подтверждения), `active`, `blocked`.
- `/start`:
  - новый пользователь → `pending` + кнопка запроса доступа + feedback,
  - `pending` → экран ожидания,
  - `blocked` → экран ограничения,
  - `active` → меню по роли.
- Админ подтверждает пользователей в разделе **👥 Пользователи** и выдаёт доступ к категориям в **🔑 Доступ к категориям**.
- Категории глобальные; доступ выдаётся через ACL (`use`/`edit`) или по owner.
- Доставка настраивается персонально в меню **🚚 Доставка** (для доступных категорий).
- Обратная связь и заявки попадают в **📥 Inbox**.

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
- `TELETHON_SESSION` — путь к Telethon-сессии (рекомендуемый вариант; используйте один и тот же для bot + collector)
- `TELETHON_SESSION_NAME` — имя сессии (используется, если `TELETHON_SESSION` указывает на директорию)
- `TELETHON_SESSION_PATH` — legacy алиас для `TELETHON_SESSION`
- `COLLECTOR_TELETHON_SESSION_NAME` — отдельная сессия для collector (если используете, задайте `UI_TELETHON_SESSION` для bot)
- `UI_TELETHON_SESSION` — путь к Telethon-сессии для bot UI (опционально)
- `TELEGRAM_BOT_TOKEN` — токен бота для /start и instant-доставки
- `TELEGRAM_ADMIN_USER_ID` — ID администратора (для debug/бот-команд, bootstrap роли)
- `ADMIN_TELEGRAM_ID` — алиас для `TELEGRAM_ADMIN_USER_ID`
- `GEMINI_API_KEY` — API-ключ Gemini (обязателен для фильтра)
- `GEMINI_MODEL` — имя модели Gemini (опционально, можно оставить пустым и использовать первую доступную `generateContent`)
- `GEMINI_COOLDOWN_SECONDS` — пауза после 429 RESOURCE_EXHAUSTED (по умолчанию 60 секунд)
- `DEFAULT_TZ` — таймзона по умолчанию (используется в delivery/daily)
- `CONFIG_SYNC_MODE` — `seed_if_empty` (по умолчанию) или `off`
- `DELIVERY_TICK_SECONDS` — частота проверки digest-расписаний (по умолчанию 60 секунд)
- `COLLECTOR_REFRESH_SECONDS` — частота обновления маршрутизации из БД (по умолчанию 30 секунд)
- `DATABASE_URL` — строка подключения к PostgreSQL (например `postgresql+psycopg://user:password@localhost:5432/pulsedidgest`)

Если используете Docker для запуска приложения, смонтируйте путь из `TELETHON_SESSION` как volume, чтобы сессия не терялась при перезапуске.

Рекомендуемый вариант без двусмысленностей: `TELETHON_SESSION=.sessions/pulsedidgest` и единый путь для bot + collector.

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

## Smoke Run (manual)

1. `docker compose up -d`
2. `alembic upgrade head`
3. `python -m apps.main`
4. В боте: создать категорию + промпт, добавить группу, сделать привязку.
5. Включить доставку (instant или digest), отправить сообщение в группе и проверить доставку/логи.

### Smoke Run (multi-user)

1. Новый пользователь → `/start` → статус `pending`.
2. Админ → **👥 Пользователи** → approve + выставить роль `user`.
3. Админ → **🔑 Доступ к категориям** → выдать `use` к категории.
4. Пользователь → **📁 Мои категории** → видит только разрешённые.
5. Пользователь → **🚚 Доставка** → включает delivery по категории.
6. Сообщение в источнике → доставляется пользователю по личной политике.
