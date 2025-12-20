"""Unified launcher for bot and collector processes."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
from typing import List


def _spawn(cmd: List[str]) -> subprocess.Popen:
    return subprocess.Popen(cmd)


def main() -> None:
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
