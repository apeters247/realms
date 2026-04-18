"""Pytest fixtures for REALMS integration tests.

Uses a real PostgreSQL test database. The database name is taken from
$REALMS_TEST_DB (default: realms_test). The test DB is created once per
session; tables are truncated between tests for isolation.
"""
from __future__ import annotations

import os
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from realms.models import Base
from realms.utils import database as db_module


def _admin_dsn() -> str:
    host = os.getenv("POSTGRES_HOST", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "estimabio")
    password = os.getenv("POSTGRES_PASSWORD", "estimabio123")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/postgres"


def _test_db_name() -> str:
    return os.getenv("REALMS_TEST_DB", "realms_test")


def _test_dsn(db_name: str) -> str:
    host = os.getenv("POSTGRES_HOST", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "estimabio")
    password = os.getenv("POSTGRES_PASSWORD", "estimabio123")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"


@pytest.fixture(scope="session")
def test_database_url() -> Iterator[str]:
    """Create (or reuse) a dedicated REALMS test database. Drop at session end."""
    db_name = _test_db_name()
    admin = create_engine(_admin_dsn(), isolation_level="AUTOCOMMIT", future=True)
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": db_name}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin.dispose()

    os.environ["POSTGRES_DB"] = db_name
    db_module.reset_engine_for_tests()

    engine = db_module.get_engine()
    Base.metadata.create_all(engine)

    yield _test_dsn(db_name)

    Base.metadata.drop_all(engine)
    engine.dispose()
    db_module.reset_engine_for_tests()


@pytest.fixture
def db_session(test_database_url) -> Iterator[Session]:
    """Yield a clean Session; truncate all REALMS tables after each test."""
    engine = db_module.get_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        with engine.begin() as conn:
            conn.execute(text(
                "TRUNCATE TABLE plant_spirit_connections, entity_relationships, entities, "
                "entity_classes, entity_categories, ingested_entities, ingestion_sources, "
                "cultures, geographic_regions RESTART IDENTITY CASCADE"
            ))


@pytest.fixture
def seeded(db_session) -> dict:
    """Populate the minimal seed fixture and return ID map."""
    from scripts.seed_realms import seed
    ids = seed(db_session)
    return ids


@pytest.fixture
def client(test_database_url) -> Iterator[TestClient]:
    """FastAPI TestClient using the test DB."""
    from realms.api.main import app
    with TestClient(app) as c:
        yield c
