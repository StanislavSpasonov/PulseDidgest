# PulseDidgest

Telegram → LLM → Signal → Delivery

Early-stage MVP.

## Telegram Collector (MVP)

1. Скопируйте `.env.example` в `.env` и заполните переменные окружения.
2. Установите зависимости: `pip install -r requirements.txt`.
3. Запустите collector командой `python apps/collector/main.py`.

Collector автоматически загружает `.env` из корня проекта (python-dotenv), берёт `TELETHON_SESSION_NAME` из env (или использует `pulsedidgest` по умолчанию) и логирует каждое новое сообщение из указанного чата в stdout.

### Переменные окружения
- `TELEGRAM_API_ID` — API ID Telegram (integer)
- `TELEGRAM_API_HASH` — соответствующий API hash
- `TELEGRAM_SOURCE_CHAT` — username или ID источника
- `TELETHON_SESSION_NAME` — имя файла сессии (опционально, по умолчанию `pulsedidgest`)
