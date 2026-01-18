"""Unified launcher for bot and collector processes."""
from __future__ import annotations

import signal
import subprocess
import sys
import logging
import os
from typing import List

from src.infrastructure.config.settings import DEFAULT_SESSION_NAME
from src.infrastructure.telegram.session_resolver import resolve_telethon_session_path


def _spawn(cmd: List[str]) -> subprocess.Popen:
    return subprocess.Popen(cmd)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("launcher")
    env = os.environ
    logger.info("Env check: DATABASE_URL present=%s", bool(env.get("DATABASE_URL")))
    logger.info("Env check: TELEGRAM_BOT_TOKEN present=%s", bool(env.get("TELEGRAM_BOT_TOKEN")))
    session_env = env.get("TELETHON_SESSION") or env.get("TELETHON_SESSION_PATH")
    session_name = env.get("TELETHON_SESSION_NAME", DEFAULT_SESSION_NAME)
    collector_override = env.get("COLLECTOR_TELETHON_SESSION_NAME")
    ui_override = env.get("UI_TELETHON_SESSION")
    collector_session = resolve_telethon_session_path(
        collector_override or session_env,
        session_name,
        default_name=DEFAULT_SESSION_NAME,
    )
    ui_session = resolve_telethon_session_path(
        ui_override or session_env or collector_override,
        session_name,
        default_name=DEFAULT_SESSION_NAME,
    )
    logger.info("Telethon session path (bot.ui)=%s", ui_session)
    logger.info("Telethon session path (collector)=%s", collector_session)

    python = sys.executable
    bot_cmd = [python, "-m", "apps.bot.main"]
    collector_cmd = [python, "-m", "apps.collector.main"]

    children: List[subprocess.Popen] = []

    def _shutdown(signum: int, _frame) -> None:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
        raise SystemExit(signum)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    children.append(_spawn(collector_cmd))
    children.append(_spawn(bot_cmd))

    exit_code = 0
    for child in children:
        code = child.wait()
        if code != 0:
            exit_code = code
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
