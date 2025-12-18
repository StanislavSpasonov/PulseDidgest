"""SQLAlchemy engine and session factory helpers."""
from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def _get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is required")
    return url


@lru_cache(maxsize=1)
def get_engine():
    """Return a singleton SQLAlchemy engine configured from env."""
    return create_engine(_get_database_url(), future=True)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker:
    """Return a cached session factory bound to the engine."""
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def get_session() -> Session:
    """Convenience helper to instantiate a new Session."""
    factory = get_session_factory()
    return factory()
