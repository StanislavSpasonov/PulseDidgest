# PulseDidgest

Telegram → LLM → Signal → Delivery

Early-stage MVP.

## Telegram Collector (MVP)

1. Скопируйте `.env.example` в `.env` и заполните `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SOURCE_CHAT`.
2. Установите зависимости, например: `pip install telethon`.
3. Запустите collector командой `python apps/collector/main.py`.

Collector берёт `TELETHON_SESSION_NAME` из env (или использует `pulsedidgest` по умолчанию) и логирует каждое новое сообщение из указанного чата в stdout.
