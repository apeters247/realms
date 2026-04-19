"""Database engine and session factory for REALMS."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def _build_dsn() -> str:
    """Compose PostgreSQL DSN from environment variables."""
    host = os.getenv("POSTGRES_HOST", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "estimabio")
    password = os.getenv("POSTGRES_PASSWORD", "estimabio123")
    db = os.getenv("POSTGRES_DB", "estimabio")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Return process-wide SQLAlchemy engine, lazily initialized."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            _build_dsn(),
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            future=True,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return process-wide session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _SessionLocal


@contextmanager
def get_db_session() -> Iterator[Session]:
    """Yield a Session; closes on exit. Caller handles commit/rollback."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def reset_engine_for_tests() -> None:
    """Test-only: discard cached engine/session so a new DSN picks up."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
