from __future__ import annotations

from pathlib import Path
from typing import Optional

DEFAULT_SESSION_DIR = ".sessions"
DEFAULT_SESSION_NAME = "pulsedidgest"


def resolve_telethon_session_path(
    session_value: str | None,
    session_name: str | None,
    default_name: str = DEFAULT_SESSION_NAME,
    default_dir: str = DEFAULT_SESSION_DIR,
) -> str:
    name = (session_name or "").strip() or default_name
    raw = (session_value or "").strip()
    if not raw:
        path = Path(default_dir) / name
        return str(path.expanduser().resolve())
    path = Path(raw).expanduser()
    if _looks_like_session_dir(path, raw, name):
        path = path / name
    return str(path.resolve())


def log_telethon_session_diagnostics(
    logger,
    session_path: str,
    label: str,
) -> None:
    path = Path(session_path)
    exists = path.exists()
    if exists and path.is_file():
        size: Optional[int] = path.stat().st_size
        kind = "file"
    elif exists and path.is_dir():
        size = None
        kind = "dir"
    else:
        size = None
        kind = "missing"
    logger.info(
        "Telethon session [%s] path=%s exists=%s type=%s size=%s",
        label,
        session_path,
        exists,
        kind,
        size if size is not None else "-",
    )


def _looks_like_session_dir(path: Path, raw: str, session_name: str) -> bool:
    if raw.endswith(("/", "\\")):
        return True
    if path.exists() and path.is_dir():
        return True
    if path.name in {".sessions", "sessions"}:
        return True
    return False
