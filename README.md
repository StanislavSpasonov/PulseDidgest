# PulseDidgest

Telegram → LLM → Signal → Delivery

Early-stage MVP.

## Telegram Collector (MVP)

1. Скопируйте `.env.example` в `.env` и заполните переменные окружения.
2. Установите зависимости: `pip install -r requirements.txt`.
3. Запустите collector командой `python apps/collector/main.py`.

Collector автоматически загружает `.env` из корня проекта (python-dotenv), берёт `TELETHON_SESSION_NAME` из env (или использует `pulsedidgest` по умолчанию), логирует каждое новое сообщение и отправляет текст в Gemini для классификации.

## Gemini Filter (MVP)

Для фильтрации используется Gemini (Google Generative AI). Collector передаёт текст сообщения и получает строго JSON-ответ вида `{ "pass": bool, "score": 0..1, "reason": "..." }`. Решение выводится в stdout и пока никак не сохраняется.

### Переменные окружения
- `TELEGRAM_API_ID` — API ID Telegram (integer)
- `TELEGRAM_API_HASH` — соответствующий API hash
- `TELEGRAM_SOURCE_CHAT` — username или ID источника
- `TELETHON_SESSION_NAME` — имя файла сессии (опционально, по умолчанию `pulsedidgest`)
- `GEMINI_API_KEY` — API-ключ Gemini (обязателен для фильтра)
