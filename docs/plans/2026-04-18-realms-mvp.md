# REALMS Phase 1: Read-Only API Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the REALMS read-only API from non-booting scaffolding to a fully working Phase 1 service backed by PostgreSQL, with seed data and integration tests, deployable via Docker Compose.

**Architecture:** FastAPI app (`realms/api/main.py`) with 9 routers (entities, classes, hierarchy, relationships, cultures, regions, sources, search, stats). SQLAlchemy 2.0 ORM models mirror the REALMS schema from `docs/DATA_MODEL.md`, persisted in the shared EstimaBio PostgreSQL instance but in REALMS-prefixed tables. Service layer encapsulates query logic. Integration tests hit a real Postgres test DB (no mocks — matches project convention).

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL 15, pytest, Docker Compose.

**Out of Scope for Phase 1 (future plans):**
- Ingestion pipeline (LLM extraction workers)
- Neo4j sync
- Web frontend (D3.js / Cytoscape.js / Leaflet)
- Alembic migration management (using `create_all()` bootstrap for MVP)
- Rate limiting middleware

---

## File Structure

**Created in this plan:**

```
realms/
├── run_realms_api.sh                  # New: Docker entrypoint script
├── realms/
│   ├── __init__.py                    # New: package marker
│   ├── api/
│   │   ├── __init__.py                # New
│   │   ├── main.py                    # Modified: timestamp import
│   │   └── routes/
│   │       ├── __init__.py            # New
│   │       ├── entities.py            # Modified: pagination envelope
│   │       ├── classes.py             # (unchanged)
│   │       ├── hierarchy.py           # (unchanged)
│   │       ├── relationships.py       # (unchanged)
│   │       ├── cultures.py            # New
│   │       ├── regions.py             # New
│   │       ├── sources.py             # New
│   │       ├── search.py              # New
│   │       └── stats.py               # New
│   ├── models/
│   │   ├── __init__.py                # New: exports Base + all models
│   │   ├── schemas.py                 # (unchanged)
│   │   └── orm.py                     # New: SQLAlchemy models
│   ├── services/
│   │   ├── __init__.py                # New
│   │   ├── entity_service.py          # New
│   │   ├── class_service.py           # New
│   │   ├── hierarchy_service.py       # New
│   │   ├── relationship_service.py    # New
│   │   ├── culture_service.py         # New
│   │   ├── region_service.py          # New
│   │   ├── source_service.py          # New
│   │   ├── search_service.py          # New
│   │   └── stats_service.py           # New
│   └── utils/
│       ├── __init__.py                # New
│       └── database.py                # New: engine + session factory
├── scripts/
│   ├── bootstrap_realms_db.py         # New: create tables + optional seed
│   └── seed_realms.py                 # New: minimal reproducible seed
└── tests/
    ├── __init__.py                    # New
    ├── conftest.py                    # New: db/client fixtures
    ├── test_entities.py               # New
    ├── test_classes.py                # New
    ├── test_hierarchy.py              # New
    ├── test_relationships.py          # New
    ├── test_cultures.py               # New
    ├── test_regions.py                # New
    ├── test_sources.py                # New
    ├── test_search.py                 # New
    └── test_stats.py                  # New
```

**Responsibilities:**
- `realms/api/routes/` — Thin HTTP adapters; parse query params, call service, return response.
- `realms/services/` — All query logic. One service per resource. Pure functions taking a `Session`.
- `realms/models/orm.py` — SQLAlchemy ORM classes matching `docs/DATA_MODEL.md`.
- `realms/models/schemas.py` — Pydantic response models (already exists).
- `realms/utils/database.py` — Engine, session factory, `get_db_session()` context manager.
- `scripts/bootstrap_realms_db.py` — Idempotent `Base.metadata.create_all()`.
- `scripts/seed_realms.py` — Minimal reproducible dataset for dev/test.
- `tests/` — pytest integration tests against a real test DB.

---

## Conventions

- **Python:** 3.11, type hints on all functions, Google-style docstrings.
- **SQLAlchemy:** 2.0 style (`Mapped[...]`, `mapped_column(...)`, `select()`).
- **Tests:** Integration-only for MVP. Real Postgres test DB. Markers: `@pytest.mark.integration`.
- **Commits:** One per task. Subject format: `feat(realms): <short>` or `fix(realms): <short>` or `test(realms): <short>`.
- **Line length:** 100 chars.
- **Working directory:** `/var/www/realms` for all commands.

---

## Task 1: Run Script + Package Markers

**Files:**
- Create: `/var/www/realms/run_realms_api.sh`
- Create: `/var/www/realms/realms/__init__.py`
- Create: `/var/www/realms/realms/api/__init__.py`
- Create: `/var/www/realms/realms/api/routes/__init__.py`
- Create: `/var/www/realms/realms/models/__init__.py`
- Create: `/var/www/realms/realms/services/__init__.py`
- Create: `/var/www/realms/realms/utils/__init__.py`
- Create: `/var/www/realms/tests/__init__.py`

- [ ] **Step 1: Create the entrypoint shell script**

Write `/var/www/realms/run_realms_api.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8001}"
LOG_LEVEL="${LOG_LEVEL:-info}"

# Bootstrap DB schema (idempotent)
python -m scripts.bootstrap_realms_db

# Launch API
exec uvicorn realms.api.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --log-level "$LOG_LEVEL"
```

- [ ] **Step 2: Make the script executable**

Run:
```bash
chmod +x /var/www/realms/run_realms_api.sh
```

- [ ] **Step 3: Create empty package marker files**

Write these 7 files with a one-line docstring each:

`/var/www/realms/realms/__init__.py`:
```python
"""REALMS package root."""
```

`/var/www/realms/realms/api/__init__.py`:
```python
"""REALMS API package."""
```

`/var/www/realms/realms/api/routes/__init__.py`:
```python
"""REALMS API routes."""
```

`/var/www/realms/realms/models/__init__.py`:
```python
"""REALMS models (ORM + Pydantic)."""
from realms.models.orm import (
    Base,
    IngestionSource,
    IngestedEntity,
    EntityCategory,
    EntityClass,
    Entity,
    EntityRelationship,
    PlantSpiritConnection,
    Culture,
    GeographicRegion,
)

__all__ = [
    "Base",
    "IngestionSource",
    "IngestedEntity",
    "EntityCategory",
    "EntityClass",
    "Entity",
    "EntityRelationship",
    "PlantSpiritConnection",
    "Culture",
    "GeographicRegion",
]
```

`/var/www/realms/realms/services/__init__.py`:
```python
"""REALMS service layer."""
```

`/var/www/realms/realms/utils/__init__.py`:
```python
"""REALMS utilities."""
```

`/var/www/realms/tests/__init__.py`:
```python
"""REALMS tests."""
```

- [ ] **Step 4: Verify structure**

Run:
```bash
ls /var/www/realms/run_realms_api.sh /var/www/realms/realms/__init__.py /var/www/realms/realms/api/__init__.py /var/www/realms/realms/api/routes/__init__.py /var/www/realms/realms/models/__init__.py /var/www/realms/realms/services/__init__.py /var/www/realms/realms/utils/__init__.py /var/www/realms/tests/__init__.py
```

Expected: all 8 paths listed with no errors.

- [ ] **Step 5: Commit**

```bash
cd /var/www/realms && \
git add run_realms_api.sh realms/__init__.py realms/api/__init__.py realms/api/routes/__init__.py realms/models/__init__.py realms/services/__init__.py realms/utils/__init__.py tests/__init__.py && \
git commit -m "feat(realms): entrypoint script and package markers"
```

---

## Task 2: Database Session Utility

**Files:**
- Create: `/var/www/realms/realms/utils/database.py`

- [ ] **Step 1: Write the session utility**

Write `/var/www/realms/realms/utils/database.py`:

```python
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
```

- [ ] **Step 2: Verify import works syntactically**

Run:
```bash
cd /var/www/realms && python -c "from realms.utils.database import get_db_session, get_engine; print('ok')"
```

Expected: prints `ok` (the engine is lazy, so no DB connection is required for import).

- [ ] **Step 3: Commit**

```bash
cd /var/www/realms && git add realms/utils/database.py && \
git commit -m "feat(realms): database engine and session factory"
```

---

## Task 3: SQLAlchemy ORM Models

**Files:**
- Create: `/var/www/realms/realms/models/orm.py`

- [ ] **Step 1: Write the ORM models**

Write `/var/www/realms/realms/models/orm.py`:

```python
"""SQLAlchemy ORM models for REALMS.

Mirrors the schema in docs/DATA_MODEL.md. Tables are created via
scripts/bootstrap_realms_db.py using Base.metadata.create_all().
"""
from __future__ import annotations

from datetime import datetime, date
from typing import Any, Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Boolean,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for REALMS ORM models."""


class IngestionSource(Base):
    __tablename__ = "ingestion_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(500), nullable=False)
    authors: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    publication_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    journal_or_venue: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    volume_issue: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pages: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    doi: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    isbn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    access_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    retrieval_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    original_language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    translation_info: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    credibility_score: Mapped[Optional[float]] = mapped_column(
        Float,
        CheckConstraint("credibility_score >= 0 AND credibility_score <= 1"),
        nullable=True,
    )
    peer_reviewed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    citation_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    altmetrics: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    ingestion_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    storage_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    access_restrictions: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ethical_considerations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    ingested_entities: Mapped[list["IngestedEntity"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class IngestedEntity(Base):
    __tablename__ = "ingested_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ingestion_sources.id", ondelete="CASCADE"), nullable=True, index=True
    )
    extraction_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    llm_model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    llm_temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    llm_prompt_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    raw_extracted_data: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    normalized_data: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    entity_name_raw: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    entity_name_normalized: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, index=True)
    extraction_confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        CheckConstraint("extraction_confidence >= 0 AND extraction_confidence <= 1"),
        nullable=True,
        index=True,
    )
    extraction_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    quote_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="raw", index=True)
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    source: Mapped[Optional[IngestionSource]] = relationship(back_populates="ingested_entities")


class EntityCategory(Base):
    __tablename__ = "entity_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entity_categories.id"), nullable=True
    )
    icon_emoji: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    provenance_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sources: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    classes: Mapped[list["EntityClass"]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )


class EntityClass(Base):
    __tablename__ = "entity_classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entity_categories.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    alternate_names: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    core_powers: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    associated_plants: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    cultural_origin: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    hierarchy_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hierarchy_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    provenance_sources: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    category: Mapped[Optional[EntityCategory]] = relationship(back_populates="classes")
    entities: Mapped[list["Entity"]] = relationship(back_populates="entity_class")


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_class_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entity_classes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    alignment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    realm: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    hierarchy_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hierarchy_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    alternate_names: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    powers: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    domains: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    associated_animals: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    plant_teachers: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    geographical_associations: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    cultural_associations: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    provenance_sources: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    extraction_instances: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    consensus_confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        CheckConstraint("consensus_confidence >= 0 AND consensus_confidence <= 1"),
        nullable=True,
        index=True,
    )
    conflict_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    entity_class: Mapped[Optional[EntityClass]] = relationship(back_populates="entities")
    outgoing_relationships: Mapped[list["EntityRelationship"]] = relationship(
        foreign_keys="EntityRelationship.source_entity_id",
        back_populates="source_entity",
        cascade="all, delete-orphan",
    )
    incoming_relationships: Mapped[list["EntityRelationship"]] = relationship(
        foreign_keys="EntityRelationship.target_entity_id",
        back_populates="target_entity",
        cascade="all, delete-orphan",
    )
    plant_connections: Mapped[list["PlantSpiritConnection"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )


class EntityRelationship(Base):
    __tablename__ = "entity_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    strength: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    provenance_sources: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    extraction_confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        CheckConstraint("extraction_confidence >= 0 AND extraction_confidence <= 1"),
        nullable=True,
    )
    cultural_context: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    historical_period: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    source_entity: Mapped[Entity] = relationship(
        foreign_keys=[source_entity_id], back_populates="outgoing_relationships"
    )
    target_entity: Mapped[Entity] = relationship(
        foreign_keys=[target_entity_id], back_populates="incoming_relationships"
    )


class PlantSpiritConnection(Base):
    __tablename__ = "plant_spirit_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Note: compound_id intentionally NOT declared as ForeignKey for Phase 1.
    # The herbalist `compounds` table is managed by EstimaBio and not guaranteed
    # to exist in every deployment. Phase 2 will add cross-schema FK.
    compound_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    preparation_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    context_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cultural_association: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    geographical_association: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    provenance_sources: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    extraction_confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        CheckConstraint("extraction_confidence >= 0 AND extraction_confidence <= 1"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    entity: Mapped[Entity] = relationship(back_populates="plant_connections")


class Culture(Base):
    __tablename__ = "cultures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    language_family: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    countries: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tradition_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    primary_plants: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    entity_pantheon: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    sources: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GeographicRegion(Base):
    __tablename__ = "geographic_regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    region_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    countries: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    center_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    center_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    boundary_geojson: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    cultural_overlap: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    endemic_entities: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    shared_entities: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    sources: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 2: Verify models import and register on Base**

Run:
```bash
cd /var/www/realms && python -c "from realms.models import Base; print(sorted(Base.metadata.tables.keys()))"
```

Expected output:
```
['cultures', 'entities', 'entity_categories', 'entity_classes', 'entity_relationships', 'geographic_regions', 'ingested_entities', 'ingestion_sources', 'plant_spirit_connections']
```

- [ ] **Step 3: Commit**

```bash
cd /var/www/realms && git add realms/models/orm.py realms/models/__init__.py && \
git commit -m "feat(realms): SQLAlchemy ORM models for all REALMS tables"
```

---

## Task 4: Bootstrap Script (create_all) + Seed Script

**Files:**
- Create: `/var/www/realms/scripts/__init__.py`
- Create: `/var/www/realms/scripts/bootstrap_realms_db.py`
- Create: `/var/www/realms/scripts/seed_realms.py`

- [ ] **Step 1: Create scripts package marker**

Write `/var/www/realms/scripts/__init__.py`:
```python
"""REALMS operational scripts."""
```

- [ ] **Step 2: Write the bootstrap script**

Write `/var/www/realms/scripts/bootstrap_realms_db.py`:

```python
"""Create REALMS tables (idempotent). Invoked at container startup."""
from __future__ import annotations

import logging
import sys

from realms.models import Base
from realms.utils.database import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("realms.bootstrap")


def main() -> int:
    engine = get_engine()
    log.info("Creating REALMS tables (if not exist) on %s", engine.url)
    Base.metadata.create_all(engine)
    created = sorted(Base.metadata.tables.keys())
    log.info("REALMS tables ready: %s", ", ".join(created))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Write the seed script**

Write `/var/www/realms/scripts/seed_realms.py`:

```python
"""Insert a minimal reproducible dataset for dev and tests.

Run only against dev/test databases. Safe to re-run: uses name-based
lookups so it won't duplicate data.
"""
from __future__ import annotations

import logging
import sys

from sqlalchemy import select

from realms.models import (
    Culture,
    Entity,
    EntityCategory,
    EntityClass,
    EntityRelationship,
    GeographicRegion,
    IngestedEntity,
    IngestionSource,
    PlantSpiritConnection,
)
from realms.utils.database import get_db_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("realms.seed")


def _get_or_create(session, model, filters: dict, defaults: dict):
    """Fetch by filters or insert with filters+defaults."""
    stmt = select(model)
    for key, value in filters.items():
        stmt = stmt.where(getattr(model, key) == value)
    instance = session.execute(stmt).scalar_one_or_none()
    if instance is not None:
        return instance
    params = {**filters, **defaults}
    instance = model(**params)
    session.add(instance)
    session.flush()
    return instance


def seed(session) -> dict:
    """Populate minimum viable fixtures. Returns created IDs."""
    amazon = _get_or_create(
        session, GeographicRegion,
        {"name": "Amazon Basin"},
        {
            "region_type": "tropical",
            "countries": ["BR", "PE", "CO", "EC", "BO"],
            "center_latitude": -3.4653,
            "center_longitude": -62.2159,
        },
    )
    yanomami = _get_or_create(
        session, Culture,
        {"name": "Yanomami"},
        {
            "language_family": "Yanomaman",
            "region": "Upper Amazon",
            "countries": ["BR", "VE"],
            "tradition_type": "shamanism",
            "primary_plants": ["Banisteriopsis caapi", "Virola theiodora"],
        },
    )
    shipibo = _get_or_create(
        session, Culture,
        {"name": "Shipibo-Konibo"},
        {
            "language_family": "Panoan",
            "region": "Upper Amazon",
            "countries": ["PE"],
            "tradition_type": "vegetalismo",
            "primary_plants": ["Banisteriopsis caapi", "Psychotria viridis"],
        },
    )

    source = _get_or_create(
        session, IngestionSource,
        {"source_name": "The Falling Sky: Words of a Yanomami Shaman"},
        {
            "source_type": "book",
            "authors": [{"name": "Davi Kopenawa", "affiliation": "Yanomami shaman"}],
            "publication_year": 2013,
            "credibility_score": 0.95,
            "peer_reviewed": True,
            "ingestion_status": "completed",
        },
    )

    plant_cat = _get_or_create(
        session, EntityCategory,
        {"name": "plant_spirit"},
        {"description": "Plant-associated teacher spirits", "icon_emoji": "🌿"},
    )
    animal_cat = _get_or_create(
        session, EntityCategory,
        {"name": "animal_ally"},
        {"description": "Animal-form ally spirits", "icon_emoji": "🐆"},
    )

    chullachaqui_class = _get_or_create(
        session, EntityClass,
        {"name": "Chullachaqui"},
        {
            "category_id": plant_cat.id,
            "description": "Forest guardian spirit in Amazonian mestizo tradition",
            "core_powers": ["protection", "misdirection", "plant_teaching"],
            "hierarchy_level": 5,
            "hierarchy_name": "guardian",
            "confidence_score": 0.85,
        },
    )
    xapiri_class = _get_or_create(
        session, EntityClass,
        {"name": "Xapiripë"},
        {
            "category_id": animal_cat.id,
            "description": "Ancestral animal spirits of Yanomami shamans",
            "core_powers": ["healing", "divination", "plant_teaching"],
            "hierarchy_level": 8,
            "hierarchy_name": "shamanic spirit",
            "confidence_score": 0.90,
        },
    )

    extraction_chullachaqui = _get_or_create(
        session, IngestedEntity,
        {"entity_name_normalized": "Chullachaqui", "source_id": source.id},
        {
            "extraction_method": "llm_prompt_v1",
            "llm_model_used": "deepseek-chat",
            "llm_temperature": 0.1,
            "llm_prompt_version": "v1",
            "entity_name_raw": "chullachaqui",
            "extraction_confidence": 0.88,
            "status": "confirmed",
        },
    )
    extraction_xapiri = _get_or_create(
        session, IngestedEntity,
        {"entity_name_normalized": "Xapiripë", "source_id": source.id},
        {
            "extraction_method": "llm_prompt_v1",
            "llm_model_used": "deepseek-chat",
            "llm_temperature": 0.1,
            "llm_prompt_version": "v1",
            "entity_name_raw": "xapiripë",
            "extraction_confidence": 0.92,
            "status": "confirmed",
        },
    )

    chullachaqui = _get_or_create(
        session, Entity,
        {"name": "Chullachaqui"},
        {
            "entity_class_id": chullachaqui_class.id,
            "entity_type": "plant_spirit",
            "alignment": "neutral",
            "realm": "forest",
            "hierarchy_level": 5,
            "hierarchy_name": "guardian",
            "description": "A shapeshifting forest guardian with one foot smaller than the other.",
            "alternate_names": {"Quechua": ["chullachaki"], "Spanish": ["dueño del monte"]},
            "powers": ["protection", "misdirection", "plant_teaching"],
            "domains": ["forest_health", "plant_knowledge"],
            "cultural_associations": ["Shipibo-Konibo"],
            "geographical_associations": ["Amazon Basin"],
            "provenance_sources": [source.id],
            "extraction_instances": [extraction_chullachaqui.id],
            "consensus_confidence": 0.88,
        },
    )
    xapiri = _get_or_create(
        session, Entity,
        {"name": "Xapiripë"},
        {
            "entity_class_id": xapiri_class.id,
            "entity_type": "animal_ally",
            "alignment": "beneficial",
            "realm": "forest",
            "hierarchy_level": 8,
            "hierarchy_name": "shamanic spirit",
            "description": "Tiny humanoid ancestral spirits that teach Yanomami shamans.",
            "alternate_names": {"Yanomami": ["xapiri", "xapiripë"]},
            "powers": ["healing", "protection", "divination", "plant_teaching"],
            "domains": ["forest_health", "spirit_world_access"],
            "cultural_associations": ["Yanomami"],
            "geographical_associations": ["Amazon Basin"],
            "provenance_sources": [source.id],
            "extraction_instances": [extraction_xapiri.id],
            "consensus_confidence": 0.95,
        },
    )

    _get_or_create(
        session, EntityRelationship,
        {
            "source_entity_id": xapiri.id,
            "target_entity_id": chullachaqui.id,
            "relationship_type": "allied_with",
        },
        {
            "description": "Cooperate in healing ceremonies in the Amazon",
            "strength": "moderate",
            "extraction_confidence": 0.8,
            "provenance_sources": [source.id],
            "cultural_context": ["Yanomami"],
        },
    )
    _get_or_create(
        session, PlantSpiritConnection,
        {"entity_id": xapiri.id, "compound_id": None, "relationship_type": "teacher_of"},
        {
            "preparation_method": "ayahuasca brew",
            "context_description": "Teaches shamans through ayahuasca ceremonies",
            "cultural_association": ["Yanomami", "Shipibo-Konibo"],
            "geographical_association": ["Amazon Basin"],
            "provenance_sources": [source.id],
            "extraction_confidence": 0.9,
        },
    )

    session.commit()
    ids = {
        "region_amazon": amazon.id,
        "culture_yanomami": yanomami.id,
        "culture_shipibo": shipibo.id,
        "source_falling_sky": source.id,
        "category_plant": plant_cat.id,
        "category_animal": animal_cat.id,
        "class_chullachaqui": chullachaqui_class.id,
        "class_xapiri": xapiri_class.id,
        "entity_chullachaqui": chullachaqui.id,
        "entity_xapiri": xapiri.id,
    }
    log.info("Seed complete: %s", ids)
    return ids


def main() -> int:
    with get_db_session() as session:
        seed(session)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Syntactic verification (no DB required)**

Run:
```bash
cd /var/www/realms && python -c "from scripts.bootstrap_realms_db import main as boot; from scripts.seed_realms import seed; print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 5: Commit**

```bash
cd /var/www/realms && git add scripts/__init__.py scripts/bootstrap_realms_db.py scripts/seed_realms.py && \
git commit -m "feat(realms): bootstrap and seed scripts"
```

---

## Task 5: Stub Missing Routers (Unblock Container Boot)

`realms/api/main.py` imports five routers that don't exist, so the container can't start. Create skeletal routers now; flesh them out in later tasks.

**Files:**
- Create: `/var/www/realms/realms/api/routes/cultures.py`
- Create: `/var/www/realms/realms/api/routes/regions.py`
- Create: `/var/www/realms/realms/api/routes/sources.py`
- Create: `/var/www/realms/realms/api/routes/search.py`
- Create: `/var/www/realms/realms/api/routes/stats.py`

- [ ] **Step 1: Write `cultures.py` stub**

Write `/var/www/realms/realms/api/routes/cultures.py`:

```python
"""Cultures API endpoints."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_cultures():
    """Stub: replaced in Task 10."""
    return {"data": [], "pagination": {"total": 0, "page": 1, "per_page": 50, "total_pages": 0}}


@router.get("/{culture_id}")
async def get_culture(culture_id: int):
    """Stub: replaced in Task 10."""
    return {"data": None}
```

- [ ] **Step 2: Write `regions.py` stub**

Write `/var/www/realms/realms/api/routes/regions.py`:

```python
"""Geographic regions API endpoints."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_regions():
    """Stub: replaced in Task 11."""
    return {"data": [], "pagination": {"total": 0, "page": 1, "per_page": 50, "total_pages": 0}}


@router.get("/{region_id}")
async def get_region(region_id: int):
    """Stub: replaced in Task 11."""
    return {"data": None}
```

- [ ] **Step 3: Write `sources.py` stub**

Write `/var/www/realms/realms/api/routes/sources.py`:

```python
"""Sources + extractions API endpoints."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_sources():
    """Stub: replaced in Task 12."""
    return {"data": [], "pagination": {"total": 0, "page": 1, "per_page": 50, "total_pages": 0}}


@router.get("/{source_id}")
async def get_source(source_id: int):
    """Stub: replaced in Task 12."""
    return {"data": None}
```

- [ ] **Step 4: Write `search.py` stub**

Write `/var/www/realms/realms/api/routes/search.py`:

```python
"""Search API endpoints."""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class AdvancedSearchRequest(BaseModel):
    filters: dict = {}
    sort: str = "-consensus_confidence"
    page: int = 1
    per_page: int = 50


@router.get("/")
async def global_search(q: str = ""):
    """Stub: replaced in Task 13."""
    return {"data": {"entities": [], "entity_classes": [], "cultures": [], "sources": []}}


@router.post("/advanced")
async def advanced_search(req: AdvancedSearchRequest):
    """Stub: replaced in Task 13."""
    return {"data": [], "pagination": {"total": 0, "page": req.page, "per_page": req.per_page, "total_pages": 0}}
```

- [ ] **Step 5: Write `stats.py` stub**

Write `/var/www/realms/realms/api/routes/stats.py`:

```python
"""Statistics API endpoints."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_stats():
    """Stub: replaced in Task 14."""
    return {"data": {
        "total_entities": 0,
        "by_type": {},
        "by_realm": {},
        "by_alignment": {},
        "by_culture": {},
        "avg_confidence": 0.0,
        "sources_processed": 0,
        "total_extractions": 0,
    }}
```

- [ ] **Step 6: Verify all imports in main.py resolve**

Run:
```bash
cd /var/www/realms && python -c "from realms.api.main import app; print([r.path for r in app.routes][:20])"
```

Expected: a list including `/entities/`, `/entity-classes/`, `/hierarchy/tree`, `/cultures/`, `/regions/`, `/sources/`, `/search/`, `/stats/`, etc. No ImportError.

- [ ] **Step 7: Commit**

```bash
cd /var/www/realms && git add realms/api/routes/cultures.py realms/api/routes/regions.py realms/api/routes/sources.py realms/api/routes/search.py realms/api/routes/stats.py && \
git commit -m "feat(realms): stub routers for cultures/regions/sources/search/stats"
```

---

## Task 6: Test Infrastructure (conftest.py)

Before implementing services, stand up the test harness. All service tests below depend on these fixtures.

**Files:**
- Create: `/var/www/realms/tests/conftest.py`

- [ ] **Step 1: Write the conftest**

Write `/var/www/realms/tests/conftest.py`:

```python
"""Pytest fixtures for REALMS integration tests.

Uses a real PostgreSQL test database. The database name is taken from
$REALMS_TEST_DB (default: estimabio_test). The test DB is created/dropped
once per session; tables are truncated between tests for isolation.
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
    return os.getenv("REALMS_TEST_DB", "estimabio_test")


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

    # Point the process-wide engine at the test DB
    os.environ["POSTGRES_DB"] = db_name
    db_module.reset_engine_for_tests()

    engine = db_module.get_engine()
    Base.metadata.create_all(engine)

    yield _test_dsn(db_name)

    # Teardown: drop all REALMS tables (leaves DB intact for reuse)
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
        # Truncate in reverse FK order
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
```

- [ ] **Step 2: Add pytest marker config**

Write `/var/www/realms/pyproject.toml` if missing, else append. Check first:

```bash
cd /var/www/realms && ls pyproject.toml 2>/dev/null || echo "NOT_FOUND"
```

If `NOT_FOUND`, write `/var/www/realms/pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "integration: integration tests that hit a real PostgreSQL database",
]
testpaths = ["tests"]
pythonpath = ["."]
```

If the file exists, use the Edit tool to append the block above to the end.

- [ ] **Step 3: Smoke-test the conftest (optional — requires running Postgres)**

If Postgres is reachable (running inside Docker or with matching env vars exported):
```bash
cd /var/www/realms && pytest tests/ -q --collect-only
```
Expected: collects zero tests (none written yet) without errors.

If Postgres is not reachable right now, skip; Task 7 will exercise it.

- [ ] **Step 4: Commit**

```bash
cd /var/www/realms && git add tests/conftest.py pyproject.toml && \
git commit -m "test(realms): pytest fixtures for real-db integration tests"
```

---

## Task 7: Entity Service (TDD Pattern-Setter)

This task establishes the TDD pattern for all subsequent services. Write tests first, watch them fail, implement, watch them pass.

**Files:**
- Create: `/var/www/realms/realms/services/entity_service.py`
- Create: `/var/www/realms/tests/test_entities.py`
- Modify: `/var/www/realms/realms/api/routes/entities.py`

- [ ] **Step 1: Write failing tests**

Write `/var/www/realms/tests/test_entities.py`:

```python
"""Integration tests for the /entities endpoint."""
import pytest


pytestmark = pytest.mark.integration


def test_list_entities_returns_seeded_data(client, seeded):
    response = client.get("/entities/")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "pagination" in body
    assert body["pagination"]["total"] == 2
    names = {e["name"] for e in body["data"]}
    assert names == {"Chullachaqui", "Xapiripë"}


def test_list_entities_filter_by_entity_type(client, seeded):
    response = client.get("/entities/?entity_type=plant_spirit")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Chullachaqui"
    assert data[0]["entity_type"] == "plant_spirit"


def test_list_entities_filter_by_alignment(client, seeded):
    response = client.get("/entities/?alignment=beneficial")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Xapiripë"


def test_list_entities_confidence_filter(client, seeded):
    response = client.get("/entities/?confidence_min=0.9")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Xapiripë"


def test_list_entities_search_q(client, seeded):
    response = client.get("/entities/?q=Xapirip")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Xapiripë"


def test_list_entities_pagination(client, seeded):
    response = client.get("/entities/?per_page=1&page=1")
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["pagination"]["total"] == 2
    assert body["pagination"]["total_pages"] == 2


def test_get_entity_detail(client, seeded):
    entity_id = seeded["entity_xapiri"]
    response = client.get(f"/entities/{entity_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Xapiripë"
    assert data["description"].startswith("Tiny humanoid")
    assert "relationships" in data
    assert "plant_connections" in data
    assert "sources" in data
    assert len(data["relationships"]["allied_with"]) == 1
    assert len(data["plant_connections"]) == 1
    assert len(data["sources"]) == 1


def test_get_entity_404(client, seeded):
    response = client.get("/entities/99999")
    assert response.status_code == 404


def test_get_entity_relationships(client, seeded):
    entity_id = seeded["entity_xapiri"]
    response = client.get(f"/entities/{entity_id}/relationships")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["relationship_type"] == "allied_with"


def test_get_entity_plant_connections(client, seeded):
    entity_id = seeded["entity_xapiri"]
    response = client.get(f"/entities/{entity_id}/plant-connections")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["relationship_type"] == "teacher_of"
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:
```bash
cd /var/www/realms && pytest tests/test_entities.py -q
```

Expected: tests fail with ImportError (EntityService doesn't exist) or 500 errors. This proves the tests exercise the missing code.

- [ ] **Step 3: Implement `EntityService`**

Write `/var/www/realms/realms/services/entity_service.py`:

```python
"""Service layer for Entity queries."""
from __future__ import annotations

import math
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from realms.models import Entity, EntityRelationship, IngestedEntity, IngestionSource, PlantSpiritConnection


_SORT_COLUMNS = {
    "name": Entity.name,
    "consensus_confidence": Entity.consensus_confidence,
    "hierarchy_level": Entity.hierarchy_level,
    "created_at": Entity.created_at,
}


def _apply_sort(stmt, sort: str):
    """Parse comma-separated sort spec like '-consensus_confidence,name'."""
    for token in sort.split(","):
        token = token.strip()
        if not token:
            continue
        descending = token.startswith("-")
        key = token.lstrip("-")
        col = _SORT_COLUMNS.get(key)
        if col is None:
            continue
        stmt = stmt.order_by(col.desc() if descending else col.asc())
    return stmt


def _entity_to_summary(e: Entity) -> dict:
    return {
        "id": e.id,
        "name": e.name,
        "entity_type": e.entity_type,
        "alignment": e.alignment,
        "realm": e.realm,
        "hierarchy_level": e.hierarchy_level,
        "hierarchy_name": e.hierarchy_name,
        "powers": e.powers or [],
        "domains": e.domains or [],
        "consensus_confidence": e.consensus_confidence or 0.0,
        "cultural_associations": e.cultural_associations or [],
        "geographical_associations": e.geographical_associations or [],
    }


class EntityService:
    """Read-only queries over entities."""

    def __init__(self, session: Session):
        self.session = session

    def list_entities(
        self,
        entity_type: Optional[str] = None,
        alignment: Optional[str] = None,
        realm: Optional[str] = None,
        hierarchy_level_min: Optional[int] = None,
        hierarchy_level_max: Optional[int] = None,
        confidence_min: Optional[float] = None,
        culture_id: Optional[int] = None,  # Reserved for Phase 2 (culture join)
        region_id: Optional[int] = None,   # Reserved for Phase 2 (region join)
        power: Optional[str] = None,
        domain: Optional[str] = None,
        q: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
        sort: str = "-consensus_confidence,name",
    ) -> tuple[list[dict], int]:
        stmt = select(Entity)

        if entity_type:
            stmt = stmt.where(Entity.entity_type == entity_type)
        if alignment:
            stmt = stmt.where(Entity.alignment == alignment)
        if realm:
            stmt = stmt.where(Entity.realm == realm)
        if hierarchy_level_min is not None:
            stmt = stmt.where(Entity.hierarchy_level >= hierarchy_level_min)
        if hierarchy_level_max is not None:
            stmt = stmt.where(Entity.hierarchy_level <= hierarchy_level_max)
        if confidence_min is not None:
            stmt = stmt.where(Entity.consensus_confidence >= confidence_min)
        if power:
            stmt = stmt.where(Entity.powers.op("?")(power))
        if domain:
            stmt = stmt.where(Entity.domains.op("?")(domain))
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    Entity.name.ilike(like),
                    Entity.description.ilike(like),
                    func.cast(Entity.alternate_names, func.cast("", Entity.name.type).type).is_(None),
                    # Fallback text search on alternate_names JSONB casted to text
                    func.cast(Entity.alternate_names, func.text()).ilike(like),
                )
            )

        total = self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()

        stmt = _apply_sort(stmt, sort)
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)

        rows = self.session.execute(stmt).scalars().all()
        return [_entity_to_summary(e) for e in rows], total

    def get_entity(self, entity_id: int) -> Optional[dict]:
        entity = self.session.get(Entity, entity_id)
        if entity is None:
            return None

        rels_out = self.session.execute(
            select(EntityRelationship).where(EntityRelationship.source_entity_id == entity_id)
        ).scalars().all()

        relationships: dict[str, list[dict]] = {}
        for rel in rels_out:
            target = self.session.get(Entity, rel.target_entity_id)
            relationships.setdefault(rel.relationship_type, []).append({
                "entity_id": rel.target_entity_id,
                "entity_name": target.name if target else None,
                "relationship_type": rel.relationship_type,
                "description": rel.description,
                "confidence": rel.extraction_confidence or 0.0,
                "sources": rel.provenance_sources or [],
                "cultural_context": rel.cultural_context or [],
            })

        pc_rows = self.session.execute(
            select(PlantSpiritConnection).where(PlantSpiritConnection.entity_id == entity_id)
        ).scalars().all()
        plant_connections = [
            {
                "compound_id": pc.compound_id,
                "compound_name": None,
                "relationship_type": pc.relationship_type,
                "preparation": pc.preparation_method,
                "confidence": pc.extraction_confidence or 0.0,
                "sources": pc.provenance_sources or [],
                "cultural_context": pc.cultural_association or [],
            }
            for pc in pc_rows
        ]

        source_ids = list(entity.provenance_sources or [])
        sources: list[dict] = []
        if source_ids:
            src_rows = self.session.execute(
                select(IngestionSource).where(IngestionSource.id.in_(source_ids))
            ).scalars().all()
            sources = [
                {
                    "id": s.id,
                    "source_name": s.source_name,
                    "source_type": s.source_type,
                    "authors": s.authors or [],
                    "publication_year": s.publication_year,
                    "credibility_score": s.credibility_score or 0.0,
                }
                for s in src_rows
            ]

        extraction_ids = list(entity.extraction_instances or [])
        extraction_details: list[dict] = []
        if extraction_ids:
            ext_rows = self.session.execute(
                select(IngestedEntity).where(IngestedEntity.id.in_(extraction_ids))
            ).scalars().all()
            extraction_details = [
                {
                    "ingested_entity_id": ie.id,
                    "extraction_method": ie.extraction_method,
                    "llm_model": ie.llm_model_used,
                    "llm_temperature": ie.llm_temperature,
                    "raw_quote": ie.quote_context,
                    "confidence": ie.extraction_confidence or 0.0,
                }
                for ie in ext_rows
            ]

        summary = _entity_to_summary(entity)
        summary.update({
            "description": entity.description,
            "alternate_names": entity.alternate_names or {},
            "relationships": relationships,
            "plant_connections": plant_connections,
            "sources": sources,
            "extraction_details": extraction_details,
            "created_at": entity.created_at,
            "updated_at": entity.updated_at,
        })
        return summary

    def get_entity_relationships(self, entity_id: int) -> list[dict]:
        rows = self.session.execute(
            select(EntityRelationship).where(EntityRelationship.source_entity_id == entity_id)
        ).scalars().all()
        return [
            {
                "id": r.id,
                "source_entity_id": r.source_entity_id,
                "target_entity_id": r.target_entity_id,
                "relationship_type": r.relationship_type,
                "description": r.description,
                "strength": r.strength,
                "confidence": r.extraction_confidence or 0.0,
                "cultural_context": r.cultural_context or [],
                "historical_period": r.historical_period or [],
            }
            for r in rows
        ]

    def get_entity_plant_connections(self, entity_id: int) -> list[dict]:
        rows = self.session.execute(
            select(PlantSpiritConnection).where(PlantSpiritConnection.entity_id == entity_id)
        ).scalars().all()
        return [
            {
                "id": pc.id,
                "entity_id": pc.entity_id,
                "compound_id": pc.compound_id,
                "relationship_type": pc.relationship_type,
                "preparation_method": pc.preparation_method,
                "context_description": pc.context_description,
                "cultural_association": pc.cultural_association or [],
                "geographical_association": pc.geographical_association or [],
                "confidence": pc.extraction_confidence or 0.0,
            }
            for pc in rows
        ]


def compute_pagination(total: int, page: int, per_page: int) -> dict:
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": math.ceil(total / per_page) if per_page else 0,
    }
```

- [ ] **Step 4: Update the entities router to return paginated envelopes**

Replace `/var/www/realms/realms/api/routes/entities.py` with:

```python
"""Entities API endpoints (read-only)."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from realms.services.entity_service import EntityService, compute_pagination
from realms.utils.database import get_db_session

router = APIRouter()


@router.get("/")
async def list_entities(
    entity_type: Optional[str] = Query(None),
    alignment: Optional[str] = Query(None),
    realm: Optional[str] = Query(None),
    hierarchy_level_min: Optional[int] = Query(None, ge=1, le=10),
    hierarchy_level_max: Optional[int] = Query(None, ge=1, le=10),
    confidence_min: Optional[float] = Query(None, ge=0.0, le=1.0),
    culture_id: Optional[int] = Query(None, gt=0),
    region_id: Optional[int] = Query(None, gt=0),
    power: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort: str = Query("-consensus_confidence,name"),
):
    """List entities with filtering and pagination."""
    try:
        with get_db_session() as session:
            service = EntityService(session)
            entities, total = service.list_entities(
                entity_type=entity_type,
                alignment=alignment,
                realm=realm,
                hierarchy_level_min=hierarchy_level_min,
                hierarchy_level_max=hierarchy_level_max,
                confidence_min=confidence_min,
                culture_id=culture_id,
                region_id=region_id,
                power=power,
                domain=domain,
                q=q,
                page=page,
                per_page=per_page,
                sort=sort,
            )
            return {"data": entities, "pagination": compute_pagination(total, page, per_page)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{entity_id}")
async def get_entity(entity_id: int):
    """Get detailed information about a specific entity."""
    with get_db_session() as session:
        service = EntityService(session)
        entity = service.get_entity(entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="Entity not found")
        return {"data": entity}


@router.get("/{entity_id}/relationships")
async def get_entity_relationships(entity_id: int):
    """Get outgoing relationships for a specific entity."""
    with get_db_session() as session:
        service = EntityService(session)
        return {"data": service.get_entity_relationships(entity_id)}


@router.get("/{entity_id}/plant-connections")
async def get_entity_plant_connections(entity_id: int):
    """Get plant-spirit connections for a specific entity."""
    with get_db_session() as session:
        service = EntityService(session)
        return {"data": service.get_entity_plant_connections(entity_id)}
```

Note: The `q` search in `EntityService.list_entities` uses a simplified `func.cast(..., func.text())` on JSONB. If SQLAlchemy rejects that syntax, replace the entire `q` block with:

```python
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    Entity.name.ilike(like),
                    Entity.description.ilike(like),
                    func.cast(Entity.alternate_names, Text()).ilike(like),
                )
            )
```

and add `from sqlalchemy import Text` at the top.

- [ ] **Step 5: Run the tests and verify they pass**

Run:
```bash
cd /var/www/realms && pytest tests/test_entities.py -v
```

Expected: all 10 tests pass.

- [ ] **Step 6: Commit**

```bash
cd /var/www/realms && git add realms/services/entity_service.py realms/api/routes/entities.py tests/test_entities.py && \
git commit -m "feat(realms): entity service with list/get/relationships/plant-connections"
```

---

## Task 8: Class Service

**Files:**
- Create: `/var/www/realms/realms/services/class_service.py`
- Create: `/var/www/realms/tests/test_classes.py`
- Modify: `/var/www/realms/realms/api/routes/classes.py`

- [ ] **Step 1: Write failing tests**

Write `/var/www/realms/tests/test_classes.py`:

```python
"""Integration tests for the /entity-classes endpoint."""
import pytest

pytestmark = pytest.mark.integration


def test_list_classes(client, seeded):
    response = client.get("/entity-classes/")
    assert response.status_code == 200
    body = response.json()
    names = {c["name"] for c in body["data"]}
    assert {"Chullachaqui", "Xapiripë"}.issubset(names)


def test_list_classes_filter_category(client, seeded):
    cat_id = seeded["category_plant"]
    response = client.get(f"/entity-classes/?category_id={cat_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Chullachaqui"


def test_get_class_detail(client, seeded):
    class_id = seeded["class_xapiri"]
    response = client.get(f"/entity-classes/{class_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Xapiripë"
    assert "entities" in data
    assert len(data["entities"]) == 1
    assert data["entities"][0]["name"] == "Xapiripë"


def test_get_class_404(client, seeded):
    response = client.get("/entity-classes/99999")
    assert response.status_code == 404


def test_get_entities_in_class(client, seeded):
    class_id = seeded["class_chullachaqui"]
    response = client.get(f"/entity-classes/{class_id}/entities")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Chullachaqui"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /var/www/realms && pytest tests/test_classes.py -q
```
Expected: failures due to missing ClassService or wrong response shape.

- [ ] **Step 3: Implement `ClassService`**

Write `/var/www/realms/realms/services/class_service.py`:

```python
"""Service layer for EntityClass queries."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from realms.models import Entity, EntityClass, IngestionSource
from realms.services.entity_service import _entity_to_summary


_SORT_COLUMNS = {
    "name": EntityClass.name,
    "hierarchy_level": EntityClass.hierarchy_level,
    "confidence_score": EntityClass.confidence_score,
}


def _apply_sort(stmt, sort: str):
    for token in sort.split(","):
        token = token.strip()
        if not token:
            continue
        descending = token.startswith("-")
        key = token.lstrip("-")
        col = _SORT_COLUMNS.get(key)
        if col is None:
            continue
        stmt = stmt.order_by(col.desc() if descending else col.asc())
    return stmt


def _class_to_response(c: EntityClass) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "category_id": c.category_id,
        "description": c.description,
        "core_powers": c.core_powers or [],
        "associated_plants": c.associated_plants or [],
        "hierarchy_level": c.hierarchy_level,
        "hierarchy_name": c.hierarchy_name,
        "confidence_score": c.confidence_score or 0.0,
    }


class ClassService:
    def __init__(self, session: Session):
        self.session = session

    def list_entity_classes(
        self,
        category_id: Optional[int] = None,
        hierarchy_level_min: Optional[int] = None,
        hierarchy_level_max: Optional[int] = None,
        confidence_min: Optional[float] = None,
        q: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
        sort: str = "name",
    ) -> tuple[list[dict], int]:
        stmt = select(EntityClass)
        if category_id is not None:
            stmt = stmt.where(EntityClass.category_id == category_id)
        if hierarchy_level_min is not None:
            stmt = stmt.where(EntityClass.hierarchy_level >= hierarchy_level_min)
        if hierarchy_level_max is not None:
            stmt = stmt.where(EntityClass.hierarchy_level <= hierarchy_level_max)
        if confidence_min is not None:
            stmt = stmt.where(EntityClass.confidence_score >= confidence_min)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(EntityClass.name.ilike(like), EntityClass.description.ilike(like)))

        total = self.session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = _apply_sort(stmt, sort).offset((page - 1) * per_page).limit(per_page)
        rows = self.session.execute(stmt).scalars().all()
        return [_class_to_response(c) for c in rows], total

    def get_entity_class(self, class_id: int) -> Optional[dict]:
        entity_class = self.session.get(EntityClass, class_id)
        if entity_class is None:
            return None

        entities = self.session.execute(
            select(Entity).where(Entity.entity_class_id == class_id)
        ).scalars().all()

        source_ids = list(entity_class.provenance_sources or [])
        provenance_sources: list[dict] = []
        if source_ids:
            src_rows = self.session.execute(
                select(IngestionSource).where(IngestionSource.id.in_(source_ids))
            ).scalars().all()
            provenance_sources = [
                {"id": s.id, "source_name": s.source_name, "credibility_score": s.credibility_score or 0.0}
                for s in src_rows
            ]

        resp = _class_to_response(entity_class)
        resp.update({
            "entities": [_entity_to_summary(e) for e in entities],
            "provenance_sources": provenance_sources,
        })
        return resp

    def get_entities_in_class(
        self, class_id: int, page: int = 1, per_page: int = 50
    ) -> tuple[list[dict], int]:
        stmt = select(Entity).where(Entity.entity_class_id == class_id)
        total = self.session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = stmt.order_by(Entity.name.asc()).offset((page - 1) * per_page).limit(per_page)
        rows = self.session.execute(stmt).scalars().all()
        return [_entity_to_summary(e) for e in rows], total
```

- [ ] **Step 4: Update the classes router to return paginated envelopes**

Replace `/var/www/realms/realms/api/routes/classes.py` with:

```python
"""Entity Classes API endpoints."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from realms.services.class_service import ClassService
from realms.services.entity_service import compute_pagination
from realms.utils.database import get_db_session

router = APIRouter()


@router.get("/")
async def list_entity_classes(
    category_id: Optional[int] = Query(None, gt=0),
    hierarchy_level_min: Optional[int] = Query(None, ge=1, le=10),
    hierarchy_level_max: Optional[int] = Query(None, ge=1, le=10),
    confidence_min: Optional[float] = Query(None, ge=0.0, le=1.0),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort: str = Query("name"),
):
    with get_db_session() as session:
        service = ClassService(session)
        classes, total = service.list_entity_classes(
            category_id=category_id,
            hierarchy_level_min=hierarchy_level_min,
            hierarchy_level_max=hierarchy_level_max,
            confidence_min=confidence_min,
            q=q, page=page, per_page=per_page, sort=sort,
        )
        return {"data": classes, "pagination": compute_pagination(total, page, per_page)}


@router.get("/{class_id}")
async def get_entity_class(class_id: int):
    with get_db_session() as session:
        service = ClassService(session)
        entity_class = service.get_entity_class(class_id)
        if entity_class is None:
            raise HTTPException(status_code=404, detail="Entity class not found")
        return {"data": entity_class}


@router.get("/{class_id}/entities")
async def get_entities_in_class(
    class_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    with get_db_session() as session:
        service = ClassService(session)
        entities, total = service.get_entities_in_class(class_id, page, per_page)
        return {"data": entities, "pagination": compute_pagination(total, page, per_page)}
```

- [ ] **Step 5: Run tests to verify pass**

```bash
cd /var/www/realms && pytest tests/test_classes.py -v
```
Expected: all 5 tests pass.

- [ ] **Step 6: Commit**

```bash
cd /var/www/realms && git add realms/services/class_service.py realms/api/routes/classes.py tests/test_classes.py && \
git commit -m "feat(realms): entity-class service with list/get/entities"
```

---

## Task 9: Hierarchy Service

**Files:**
- Create: `/var/www/realms/realms/services/hierarchy_service.py`
- Create: `/var/www/realms/tests/test_hierarchy.py`
- Modify: `/var/www/realms/realms/api/routes/hierarchy.py`

- [ ] **Step 1: Write failing tests**

Write `/var/www/realms/tests/test_hierarchy.py`:

```python
"""Integration tests for the /hierarchy endpoints."""
import pytest

pytestmark = pytest.mark.integration


def test_hierarchy_tree(client, seeded):
    response = client.get("/hierarchy/tree")
    assert response.status_code == 200
    tree = response.json()["data"]
    assert tree["name"] == "root"
    cat_names = {c["name"] for c in tree["children"]}
    assert {"plant_spirit", "animal_ally"}.issubset(cat_names)
    plant_cat = next(c for c in tree["children"] if c["name"] == "plant_spirit")
    class_names = {c["name"] for c in plant_cat["children"]}
    assert "Chullachaqui" in class_names


def test_hierarchy_tree_filter_realm(client, seeded):
    response = client.get("/hierarchy/tree?realm=forest")
    assert response.status_code == 200
    tree = response.json()["data"]
    # Both seed entities are in forest — both categories should appear
    assert len(tree["children"]) >= 2


def test_hierarchy_flat(client, seeded):
    response = client.get("/hierarchy/flat")
    assert response.status_code == 200
    items = response.json()["data"]
    names = {i["name"] for i in items}
    assert {"Chullachaqui", "Xapiripë"}.issubset(names)
    chul = next(i for i in items if i["name"] == "Chullachaqui")
    assert chul["path"][-1] == "Chullachaqui"


def test_hierarchy_path_for_entity(client, seeded):
    entity_id = seeded["entity_xapiri"]
    response = client.get(f"/hierarchy/path/{entity_id}")
    assert response.status_code == 200
    path = response.json()["data"]
    assert path[-1] == "Xapiripë"
    assert "animal_ally" in path


def test_hierarchy_path_404(client, seeded):
    response = client.get("/hierarchy/path/99999")
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /var/www/realms && pytest tests/test_hierarchy.py -q
```

- [ ] **Step 3: Implement `HierarchyService`**

Write `/var/www/realms/realms/services/hierarchy_service.py`:

```python
"""Service layer for hierarchy tree/flat queries."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from realms.models import Entity, EntityCategory, EntityClass


class HierarchyService:
    def __init__(self, session: Session):
        self.session = session

    def _filter_entities_stmt(
        self,
        q: Optional[str],
        realm: Optional[str],
        culture_id: Optional[int],
    ):
        stmt = select(Entity)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Entity.name.ilike(like), Entity.description.ilike(like)))
        if realm:
            stmt = stmt.where(Entity.realm == realm)
        # culture_id reserved for Phase 2 (needs join table)
        return stmt

    def get_hierarchy_tree(
        self,
        q: Optional[str] = None,
        realm: Optional[str] = None,
        culture_id: Optional[int] = None,
    ) -> dict:
        entities = self.session.execute(
            self._filter_entities_stmt(q, realm, culture_id)
        ).scalars().all()

        class_ids = {e.entity_class_id for e in entities if e.entity_class_id is not None}
        classes = self.session.execute(
            select(EntityClass).where(EntityClass.id.in_(class_ids)) if class_ids else select(EntityClass).where(False)
        ).scalars().all() if class_ids else []

        cat_ids = {c.category_id for c in classes if c.category_id is not None}
        categories = self.session.execute(
            select(EntityCategory).where(EntityCategory.id.in_(cat_ids)) if cat_ids else select(EntityCategory).where(False)
        ).scalars().all() if cat_ids else []

        entities_by_class: dict[int, list[Entity]] = {}
        for e in entities:
            if e.entity_class_id is not None:
                entities_by_class.setdefault(e.entity_class_id, []).append(e)

        classes_by_cat: dict[int, list[EntityClass]] = {}
        for c in classes:
            if c.category_id is not None:
                classes_by_cat.setdefault(c.category_id, []).append(c)

        tree_children = []
        for cat in sorted(categories, key=lambda x: x.name):
            cat_children = []
            for cls in sorted(classes_by_cat.get(cat.id, []), key=lambda x: x.name):
                class_entities = entities_by_class.get(cls.id, [])
                cat_children.append({
                    "id": cls.id,
                    "name": cls.name,
                    "type": "class",
                    "entity_count": len(class_entities),
                    "children": [
                        {
                            "id": e.id,
                            "name": e.name,
                            "type": "entity",
                            "entity_count": 0,
                            "children": [],
                            "meta": {"confidence": e.consensus_confidence or 0.0},
                        }
                        for e in sorted(class_entities, key=lambda x: x.name)
                    ],
                    "meta": {"confidence": cls.confidence_score or 0.0},
                })
            tree_children.append({
                "id": cat.id,
                "name": cat.name,
                "type": "category",
                "entity_count": sum(c["entity_count"] for c in cat_children),
                "children": cat_children,
                "meta": {},
            })

        return {"name": "root", "children": tree_children}

    def get_hierarchy_flat(
        self,
        q: Optional[str] = None,
        realm: Optional[str] = None,
        culture_id: Optional[int] = None,
    ) -> list[dict]:
        tree = self.get_hierarchy_tree(q=q, realm=realm, culture_id=culture_id)
        flat: list[dict] = []

        def walk(node: dict, path: list[str], level: int):
            if node.get("type") in {"category", "class", "entity"}:
                flat.append({
                    "id": node["id"],
                    "name": node["name"],
                    "level": level,
                    "path": path + [node["name"]],
                    "entity_count": node.get("entity_count", 0),
                    "confidence": node.get("meta", {}).get("confidence", 0.0),
                })
            for child in node.get("children", []):
                walk(child, path + [node["name"]] if node.get("name") != "root" else path, level + 1)

        for child in tree["children"]:
            walk(child, [], 1)

        return flat

    def get_entity_hierarchy_path(self, entity_id: int) -> Optional[list[str]]:
        entity = self.session.get(Entity, entity_id)
        if entity is None:
            return None
        path: list[str] = []
        if entity.entity_class_id is not None:
            cls = self.session.get(EntityClass, entity.entity_class_id)
            if cls and cls.category_id is not None:
                cat = self.session.get(EntityCategory, cls.category_id)
                if cat:
                    path.append(cat.name)
            if cls:
                path.append(cls.name)
        path.append(entity.name)
        return path
```

- [ ] **Step 4: Update the hierarchy router**

Replace `/var/www/realms/realms/api/routes/hierarchy.py` with:

```python
"""Hierarchy API endpoints."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from realms.services.hierarchy_service import HierarchyService
from realms.utils.database import get_db_session

router = APIRouter()


@router.get("/tree")
async def get_hierarchy_tree(
    q: Optional[str] = Query(None),
    realm: Optional[str] = Query(None),
    culture_id: Optional[int] = Query(None, gt=0),
):
    with get_db_session() as session:
        service = HierarchyService(session)
        return {"data": service.get_hierarchy_tree(q=q, realm=realm, culture_id=culture_id)}


@router.get("/flat")
async def get_hierarchy_flat(
    q: Optional[str] = Query(None),
    realm: Optional[str] = Query(None),
    culture_id: Optional[int] = Query(None, gt=0),
):
    with get_db_session() as session:
        service = HierarchyService(session)
        return {"data": service.get_hierarchy_flat(q=q, realm=realm, culture_id=culture_id)}


@router.get("/path/{entity_id}")
async def get_entity_hierarchy_path(entity_id: int):
    with get_db_session() as session:
        service = HierarchyService(session)
        path = service.get_entity_hierarchy_path(entity_id)
        if path is None:
            raise HTTPException(status_code=404, detail="Entity not found")
        return {"data": path}
```

- [ ] **Step 5: Run tests to verify pass**

```bash
cd /var/www/realms && pytest tests/test_hierarchy.py -v
```

- [ ] **Step 6: Commit**

```bash
cd /var/www/realms && git add realms/services/hierarchy_service.py realms/api/routes/hierarchy.py tests/test_hierarchy.py && \
git commit -m "feat(realms): hierarchy service with tree/flat/path"
```

---

## Task 10: Relationship Service

**Files:**
- Create: `/var/www/realms/realms/services/relationship_service.py`
- Create: `/var/www/realms/tests/test_relationships.py`
- Modify: `/var/www/realms/realms/api/routes/relationships.py`

- [ ] **Step 1: Write failing tests**

Write `/var/www/realms/tests/test_relationships.py`:

```python
"""Integration tests for the /relationships endpoint."""
import pytest

pytestmark = pytest.mark.integration


def test_list_relationships(client, seeded):
    response = client.get("/relationships/")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["relationship_type"] == "allied_with"


def test_list_relationships_filter_by_type(client, seeded):
    response = client.get("/relationships/?relationship_type=allied_with")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


def test_list_relationships_filter_missing(client, seeded):
    response = client.get("/relationships/?relationship_type=enemy_of")
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_get_relationship_detail(client, seeded):
    list_resp = client.get("/relationships/").json()["data"]
    rel_id = list_resp[0]["id"]
    response = client.get(f"/relationships/{rel_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["relationship_type"] == "allied_with"
    assert "source_entity" in data
    assert "target_entity" in data
    assert data["source_entity"]["name"] == "Xapiripë"
    assert data["target_entity"]["name"] == "Chullachaqui"


def test_get_relationship_404(client, seeded):
    response = client.get("/relationships/99999")
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /var/www/realms && pytest tests/test_relationships.py -q
```

- [ ] **Step 3: Implement `RelationshipService`**

Write `/var/www/realms/realms/services/relationship_service.py`:

```python
"""Service layer for EntityRelationship queries."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from realms.models import Entity, EntityRelationship, IngestedEntity, IngestionSource
from realms.services.entity_service import _entity_to_summary


_SORT_COLUMNS = {
    "confidence": EntityRelationship.extraction_confidence,
    "created_at": EntityRelationship.created_at,
}


def _apply_sort(stmt, sort: str):
    for token in sort.split(","):
        token = token.strip()
        if not token:
            continue
        descending = token.startswith("-")
        key = token.lstrip("-")
        col = _SORT_COLUMNS.get(key)
        if col is None:
            continue
        stmt = stmt.order_by(col.desc() if descending else col.asc())
    return stmt


def _rel_to_response(r: EntityRelationship) -> dict:
    return {
        "id": r.id,
        "source_entity_id": r.source_entity_id,
        "target_entity_id": r.target_entity_id,
        "relationship_type": r.relationship_type,
        "description": r.description,
        "strength": r.strength,
        "confidence": r.extraction_confidence or 0.0,
        "cultural_context": r.cultural_context or [],
        "historical_period": r.historical_period or [],
    }


class RelationshipService:
    def __init__(self, session: Session):
        self.session = session

    def list_relationships(
        self,
        relationship_type: Optional[str] = None,
        source_entity_id: Optional[int] = None,
        target_entity_id: Optional[int] = None,
        confidence_min: Optional[float] = None,
        cultural_context: Optional[str] = None,
        historical_period: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
        sort: str = "-confidence",
    ) -> tuple[list[dict], int]:
        stmt = select(EntityRelationship)
        if relationship_type:
            stmt = stmt.where(EntityRelationship.relationship_type == relationship_type)
        if source_entity_id is not None:
            stmt = stmt.where(EntityRelationship.source_entity_id == source_entity_id)
        if target_entity_id is not None:
            stmt = stmt.where(EntityRelationship.target_entity_id == target_entity_id)
        if confidence_min is not None:
            stmt = stmt.where(EntityRelationship.extraction_confidence >= confidence_min)
        if cultural_context:
            stmt = stmt.where(EntityRelationship.cultural_context.op("?")(cultural_context))
        if historical_period:
            stmt = stmt.where(EntityRelationship.historical_period.op("?")(historical_period))

        total = self.session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        stmt = _apply_sort(stmt, sort).offset((page - 1) * per_page).limit(per_page)
        rows = self.session.execute(stmt).scalars().all()
        return [_rel_to_response(r) for r in rows], total

    def get_relationship(self, relationship_id: int) -> Optional[dict]:
        rel = self.session.get(EntityRelationship, relationship_id)
        if rel is None:
            return None
        source = self.session.get(Entity, rel.source_entity_id)
        target = self.session.get(Entity, rel.target_entity_id)

        source_ids = list(rel.provenance_sources or [])
        provenance_sources: list[dict] = []
        if source_ids:
            src_rows = self.session.execute(
                select(IngestionSource).where(IngestionSource.id.in_(source_ids))
            ).scalars().all()
            provenance_sources = [
                {"id": s.id, "source_name": s.source_name, "credibility_score": s.credibility_score or 0.0}
                for s in src_rows
            ]

        resp = _rel_to_response(rel)
        resp.update({
            "source_entity": _entity_to_summary(source) if source else None,
            "target_entity": _entity_to_summary(target) if target else None,
            "provenance_sources": provenance_sources,
            "extraction_details": [],
        })
        return resp
```

- [ ] **Step 4: Update the relationships router**

Replace `/var/www/realms/realms/api/routes/relationships.py` with:

```python
"""Relationships API endpoints."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from realms.services.entity_service import compute_pagination
from realms.services.relationship_service import RelationshipService
from realms.utils.database import get_db_session

router = APIRouter()


@router.get("/")
async def list_relationships(
    relationship_type: Optional[str] = Query(None),
    source_entity_id: Optional[int] = Query(None, gt=0),
    target_entity_id: Optional[int] = Query(None, gt=0),
    confidence_min: Optional[float] = Query(None, ge=0.0, le=1.0),
    cultural_context: Optional[str] = Query(None),
    historical_period: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort: str = Query("-confidence"),
):
    with get_db_session() as session:
        service = RelationshipService(session)
        rels, total = service.list_relationships(
            relationship_type=relationship_type,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            confidence_min=confidence_min,
            cultural_context=cultural_context,
            historical_period=historical_period,
            page=page, per_page=per_page, sort=sort,
        )
        return {"data": rels, "pagination": compute_pagination(total, page, per_page)}


@router.get("/{relationship_id}")
async def get_relationship(relationship_id: int):
    with get_db_session() as session:
        service = RelationshipService(session)
        rel = service.get_relationship(relationship_id)
        if rel is None:
            raise HTTPException(status_code=404, detail="Relationship not found")
        return {"data": rel}
```

- [ ] **Step 5: Run tests to verify pass**

```bash
cd /var/www/realms && pytest tests/test_relationships.py -v
```

- [ ] **Step 6: Commit**

```bash
cd /var/www/realms && git add realms/services/relationship_service.py realms/api/routes/relationships.py tests/test_relationships.py && \
git commit -m "feat(realms): relationship service with list/get"
```

---

## Task 11: Culture Service + Route

**Files:**
- Create: `/var/www/realms/realms/services/culture_service.py`
- Create: `/var/www/realms/tests/test_cultures.py`
- Modify: `/var/www/realms/realms/api/routes/cultures.py`

- [ ] **Step 1: Write failing tests**

Write `/var/www/realms/tests/test_cultures.py`:

```python
"""Integration tests for /cultures endpoints."""
import pytest

pytestmark = pytest.mark.integration


def test_list_cultures(client, seeded):
    response = client.get("/cultures/")
    assert response.status_code == 200
    body = response.json()
    names = {c["name"] for c in body["data"]}
    assert {"Yanomami", "Shipibo-Konibo"}.issubset(names)


def test_list_cultures_filter_region(client, seeded):
    response = client.get("/cultures/?region=Upper Amazon")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 2


def test_list_cultures_filter_tradition(client, seeded):
    response = client.get("/cultures/?tradition_type=vegetalismo")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Shipibo-Konibo"


def test_get_culture_detail(client, seeded):
    cid = seeded["culture_yanomami"]
    response = client.get(f"/cultures/{cid}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Yanomami"
    # Entities linked via cultural_associations JSONB
    entity_names = {e["name"] for e in data["entities"]}
    assert "Xapiripë" in entity_names


def test_get_culture_404(client, seeded):
    response = client.get("/cultures/99999")
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /var/www/realms && pytest tests/test_cultures.py -q
```

- [ ] **Step 3: Implement `CultureService`**

Write `/var/www/realms/realms/services/culture_service.py`:

```python
"""Service layer for Culture queries."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from realms.models import Culture, Entity, IngestionSource
from realms.services.entity_service import _entity_to_summary


def _culture_to_response(c: Culture) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "language_family": c.language_family,
        "region": c.region,
        "countries": c.countries or [],
        "description": c.description,
        "tradition_type": c.tradition_type,
        "primary_plants": c.primary_plants or [],
    }


class CultureService:
    def __init__(self, session: Session):
        self.session = session

    def list_cultures(
        self,
        region: Optional[str] = None,
        tradition_type: Optional[str] = None,
        language_family: Optional[str] = None,
        q: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
        sort: str = "name",
    ) -> tuple[list[dict], int]:
        stmt = select(Culture)
        if region:
            stmt = stmt.where(Culture.region == region)
        if tradition_type:
            stmt = stmt.where(Culture.tradition_type == tradition_type)
        if language_family:
            stmt = stmt.where(Culture.language_family == language_family)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Culture.name.ilike(like), Culture.description.ilike(like)))

        total = self.session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

        descending = sort.startswith("-")
        key = sort.lstrip("-")
        col = Culture.name if key not in {"region", "tradition_type"} else getattr(Culture, key)
        stmt = stmt.order_by(col.desc() if descending else col.asc())
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        rows = self.session.execute(stmt).scalars().all()
        return [_culture_to_response(c) for c in rows], total

    def get_culture(self, culture_id: int) -> Optional[dict]:
        culture = self.session.get(Culture, culture_id)
        if culture is None:
            return None

        # Entities whose cultural_associations JSONB array contains this culture's name
        entities = self.session.execute(
            select(Entity).where(Entity.cultural_associations.op("?")(culture.name))
        ).scalars().all()

        source_ids = list(culture.sources or [])
        sources: list[dict] = []
        if source_ids:
            src_rows = self.session.execute(
                select(IngestionSource).where(IngestionSource.id.in_(source_ids))
            ).scalars().all()
            sources = [
                {"id": s.id, "source_name": s.source_name, "credibility_score": s.credibility_score or 0.0}
                for s in src_rows
            ]

        resp = _culture_to_response(culture)
        resp.update({
            "entities": [_entity_to_summary(e) for e in entities],
            "entity_pantheon": culture.entity_pantheon or {},
            "sources": sources,
        })
        return resp
```

- [ ] **Step 4: Replace the cultures router**

Replace `/var/www/realms/realms/api/routes/cultures.py` with:

```python
"""Cultures API endpoints."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from realms.services.culture_service import CultureService
from realms.services.entity_service import compute_pagination
from realms.utils.database import get_db_session

router = APIRouter()


@router.get("/")
async def list_cultures(
    region: Optional[str] = Query(None),
    tradition_type: Optional[str] = Query(None),
    language_family: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort: str = Query("name"),
):
    with get_db_session() as session:
        service = CultureService(session)
        cultures, total = service.list_cultures(
            region=region, tradition_type=tradition_type,
            language_family=language_family, q=q,
            page=page, per_page=per_page, sort=sort,
        )
        return {"data": cultures, "pagination": compute_pagination(total, page, per_page)}


@router.get("/{culture_id}")
async def get_culture(culture_id: int):
    with get_db_session() as session:
        service = CultureService(session)
        culture = service.get_culture(culture_id)
        if culture is None:
            raise HTTPException(status_code=404, detail="Culture not found")
        return {"data": culture}
```

- [ ] **Step 5: Run tests to verify pass**

```bash
cd /var/www/realms && pytest tests/test_cultures.py -v
```

- [ ] **Step 6: Commit**

```bash
cd /var/www/realms && git add realms/services/culture_service.py realms/api/routes/cultures.py tests/test_cultures.py && \
git commit -m "feat(realms): culture service with list/get"
```

---

## Task 12: Region Service + Route

**Files:**
- Create: `/var/www/realms/realms/services/region_service.py`
- Create: `/var/www/realms/tests/test_regions.py`
- Modify: `/var/www/realms/realms/api/routes/regions.py`

- [ ] **Step 1: Write failing tests**

Write `/var/www/realms/tests/test_regions.py`:

```python
"""Integration tests for /regions endpoints."""
import pytest

pytestmark = pytest.mark.integration


def test_list_regions(client, seeded):
    response = client.get("/regions/")
    assert response.status_code == 200
    names = {r["name"] for r in response.json()["data"]}
    assert "Amazon Basin" in names


def test_list_regions_filter_type(client, seeded):
    response = client.get("/regions/?region_type=tropical")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Amazon Basin"


def test_get_region_detail(client, seeded):
    rid = seeded["region_amazon"]
    response = client.get(f"/regions/{rid}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Amazon Basin"
    entity_names = {e["name"] for e in data["entities"]}
    assert {"Chullachaqui", "Xapiripë"}.issubset(entity_names)


def test_get_region_404(client, seeded):
    response = client.get("/regions/99999")
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /var/www/realms && pytest tests/test_regions.py -q
```

- [ ] **Step 3: Implement `RegionService`**

Write `/var/www/realms/realms/services/region_service.py`:

```python
"""Service layer for GeographicRegion queries."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from realms.models import Entity, GeographicRegion, IngestionSource
from realms.services.entity_service import _entity_to_summary


def _region_to_response(r: GeographicRegion) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "region_type": r.region_type,
        "countries": r.countries or [],
        "center_latitude": r.center_latitude,
        "center_longitude": r.center_longitude,
        "boundary_geojson": r.boundary_geojson,
        "cultural_overlap": r.cultural_overlap or [],
        "endemic_entities": r.endemic_entities or [],
        "shared_entities": r.shared_entities or [],
    }


class RegionService:
    def __init__(self, session: Session):
        self.session = session

    def list_regions(
        self,
        region_type: Optional[str] = None,
        q: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
        sort: str = "name",
    ) -> tuple[list[dict], int]:
        stmt = select(GeographicRegion)
        if region_type:
            stmt = stmt.where(GeographicRegion.region_type == region_type)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(GeographicRegion.name.ilike(like))

        total = self.session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        descending = sort.startswith("-")
        col = GeographicRegion.name
        stmt = stmt.order_by(col.desc() if descending else col.asc())
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        rows = self.session.execute(stmt).scalars().all()
        return [_region_to_response(r) for r in rows], total

    def get_region(self, region_id: int) -> Optional[dict]:
        region = self.session.get(GeographicRegion, region_id)
        if region is None:
            return None

        entities = self.session.execute(
            select(Entity).where(Entity.geographical_associations.op("?")(region.name))
        ).scalars().all()

        source_ids = list(region.sources or [])
        sources: list[dict] = []
        if source_ids:
            src_rows = self.session.execute(
                select(IngestionSource).where(IngestionSource.id.in_(source_ids))
            ).scalars().all()
            sources = [
                {"id": s.id, "source_name": s.source_name, "credibility_score": s.credibility_score or 0.0}
                for s in src_rows
            ]

        resp = _region_to_response(region)
        resp.update({
            "entities": [_entity_to_summary(e) for e in entities],
            "sources": sources,
        })
        return resp
```

- [ ] **Step 4: Replace the regions router**

Replace `/var/www/realms/realms/api/routes/regions.py` with:

```python
"""Geographic regions API endpoints."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from realms.services.entity_service import compute_pagination
from realms.services.region_service import RegionService
from realms.utils.database import get_db_session

router = APIRouter()


@router.get("/")
async def list_regions(
    region_type: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort: str = Query("name"),
):
    with get_db_session() as session:
        service = RegionService(session)
        regions, total = service.list_regions(
            region_type=region_type, q=q, page=page, per_page=per_page, sort=sort,
        )
        return {"data": regions, "pagination": compute_pagination(total, page, per_page)}


@router.get("/{region_id}")
async def get_region(region_id: int):
    with get_db_session() as session:
        service = RegionService(session)
        region = service.get_region(region_id)
        if region is None:
            raise HTTPException(status_code=404, detail="Region not found")
        return {"data": region}
```

- [ ] **Step 5: Run tests to verify pass**

```bash
cd /var/www/realms && pytest tests/test_regions.py -v
```

- [ ] **Step 6: Commit**

```bash
cd /var/www/realms && git add realms/services/region_service.py realms/api/routes/regions.py tests/test_regions.py && \
git commit -m "feat(realms): region service with list/get"
```

---

## Task 13: Source Service + Extraction Endpoint

**Files:**
- Create: `/var/www/realms/realms/services/source_service.py`
- Create: `/var/www/realms/tests/test_sources.py`
- Modify: `/var/www/realms/realms/api/routes/sources.py`
- Modify: `/var/www/realms/realms/api/main.py` (mount extraction sub-routes)

- [ ] **Step 1: Write failing tests**

Write `/var/www/realms/tests/test_sources.py`:

```python
"""Integration tests for /sources and /extractions endpoints."""
import pytest

pytestmark = pytest.mark.integration


def test_list_sources(client, seeded):
    response = client.get("/sources/")
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["data"][0]["source_name"].startswith("The Falling Sky")


def test_list_sources_filter_type(client, seeded):
    response = client.get("/sources/?source_type=book")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


def test_list_sources_filter_peer_reviewed(client, seeded):
    response = client.get("/sources/?peer_reviewed=true")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


def test_get_source_detail(client, seeded):
    sid = seeded["source_falling_sky"]
    response = client.get(f"/sources/{sid}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["source_name"].startswith("The Falling Sky")
    assert len(data["ingested_entities"]) == 2
    assert data["extraction_statistics"]["count"] == 2


def test_get_source_404(client, seeded):
    response = client.get("/sources/99999")
    assert response.status_code == 404


def test_get_extraction_detail(client, seeded):
    # Get one extraction id via source detail
    sid = seeded["source_falling_sky"]
    source = client.get(f"/sources/{sid}").json()["data"]
    ext_id = source["ingested_entities"][0]["id"]
    response = client.get(f"/extractions/{ext_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["entity_name_normalized"] in {"Chullachaqui", "Xapiripë"}


def test_get_extraction_404(client, seeded):
    response = client.get("/extractions/99999")
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /var/www/realms && pytest tests/test_sources.py -q
```

- [ ] **Step 3: Implement `SourceService`**

Write `/var/www/realms/realms/services/source_service.py`:

```python
"""Service layer for IngestionSource + IngestedEntity queries."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from realms.models import IngestedEntity, IngestionSource


def _source_to_response(s: IngestionSource) -> dict:
    return {
        "id": s.id,
        "source_type": s.source_type,
        "source_name": s.source_name,
        "authors": s.authors or [],
        "publication_year": s.publication_year,
        "journal_or_venue": s.journal_or_venue,
        "volume_issue": s.volume_issue,
        "pages": s.pages,
        "doi": s.doi,
        "isbn": s.isbn,
        "url": s.url,
        "access_date": s.access_date,
        "retrieval_method": s.retrieval_method,
        "language": s.language,
        "original_language": s.original_language,
        "translation_info": s.translation_info,
        "credibility_score": s.credibility_score or 0.0,
        "peer_reviewed": bool(s.peer_reviewed),
        "citation_count": s.citation_count or 0,
        "altmetrics": s.altmetrics,
        "ingestion_status": s.ingestion_status,
        "ingested_at": s.ingested_at,
        "processed_at": s.processed_at,
        "error_log": s.error_log,
        "raw_content_hash": s.raw_content_hash,
        "storage_path": s.storage_path,
        "access_restrictions": s.access_restrictions,
        "ethical_considerations": s.ethical_considerations,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
    }


def _extraction_to_response(e: IngestedEntity) -> dict:
    return {
        "id": e.id,
        "source_id": e.source_id,
        "extraction_method": e.extraction_method,
        "llm_model_used": e.llm_model_used,
        "llm_temperature": e.llm_temperature,
        "llm_prompt_version": e.llm_prompt_version,
        "raw_extracted_data": e.raw_extracted_data or {},
        "normalized_data": e.normalized_data or {},
        "entity_name_raw": e.entity_name_raw,
        "entity_name_normalized": e.entity_name_normalized,
        "extraction_confidence": e.extraction_confidence or 0.0,
        "extraction_context": e.extraction_context,
        "page_number": e.page_number,
        "section_title": e.section_title,
        "quote_context": e.quote_context,
        "status": e.status,
        "reviewer_notes": e.reviewer_notes,
        "reviewed_by": e.reviewed_by,
        "reviewed_at": e.reviewed_at,
        "created_at": e.created_at,
        "updated_at": e.updated_at,
    }


class SourceService:
    def __init__(self, session: Session):
        self.session = session

    def list_sources(
        self,
        source_type: Optional[str] = None,
        publication_year_min: Optional[int] = None,
        publication_year_max: Optional[int] = None,
        peer_reviewed: Optional[bool] = None,
        credibility_min: Optional[float] = None,
        ingestion_status: Optional[str] = None,
        q: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
        sort: str = "-publication_year",
    ) -> tuple[list[dict], int]:
        stmt = select(IngestionSource)
        if source_type:
            stmt = stmt.where(IngestionSource.source_type == source_type)
        if publication_year_min is not None:
            stmt = stmt.where(IngestionSource.publication_year >= publication_year_min)
        if publication_year_max is not None:
            stmt = stmt.where(IngestionSource.publication_year <= publication_year_max)
        if peer_reviewed is not None:
            stmt = stmt.where(IngestionSource.peer_reviewed == peer_reviewed)
        if credibility_min is not None:
            stmt = stmt.where(IngestionSource.credibility_score >= credibility_min)
        if ingestion_status:
            stmt = stmt.where(IngestionSource.ingestion_status == ingestion_status)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(
                IngestionSource.source_name.ilike(like),
                IngestionSource.doi.ilike(like),
            ))

        total = self.session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

        descending = sort.startswith("-")
        key = sort.lstrip("-")
        col = getattr(IngestionSource, key, IngestionSource.publication_year)
        stmt = stmt.order_by(col.desc() if descending else col.asc())
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        rows = self.session.execute(stmt).scalars().all()
        return [_source_to_response(s) for s in rows], total

    def get_source(self, source_id: int) -> Optional[dict]:
        source = self.session.get(IngestionSource, source_id)
        if source is None:
            return None
        ext_rows = self.session.execute(
            select(IngestedEntity).where(IngestedEntity.source_id == source_id)
        ).scalars().all()

        resp = _source_to_response(source)
        resp.update({
            "ingested_entities": [
                {
                    "id": e.id,
                    "entity_name_normalized": e.entity_name_normalized,
                    "extraction_confidence": e.extraction_confidence or 0.0,
                    "status": e.status,
                }
                for e in ext_rows
            ],
            "extraction_statistics": {
                "count": len(ext_rows),
                "avg_confidence": (
                    sum(e.extraction_confidence or 0.0 for e in ext_rows) / len(ext_rows)
                    if ext_rows else 0.0
                ),
            },
        })
        return resp

    def get_extraction(self, extraction_id: int) -> Optional[dict]:
        ext = self.session.get(IngestedEntity, extraction_id)
        if ext is None:
            return None
        return _extraction_to_response(ext)
```

- [ ] **Step 4: Replace the sources router AND add an extractions router**

Replace `/var/www/realms/realms/api/routes/sources.py` with:

```python
"""Sources and extractions API endpoints."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from realms.services.entity_service import compute_pagination
from realms.services.source_service import SourceService
from realms.utils.database import get_db_session

router = APIRouter()
extractions_router = APIRouter()


@router.get("/")
async def list_sources(
    source_type: Optional[str] = Query(None),
    publication_year_min: Optional[int] = Query(None),
    publication_year_max: Optional[int] = Query(None),
    peer_reviewed: Optional[bool] = Query(None),
    credibility_min: Optional[float] = Query(None, ge=0.0, le=1.0),
    ingestion_status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort: str = Query("-publication_year"),
):
    with get_db_session() as session:
        service = SourceService(session)
        sources, total = service.list_sources(
            source_type=source_type,
            publication_year_min=publication_year_min,
            publication_year_max=publication_year_max,
            peer_reviewed=peer_reviewed,
            credibility_min=credibility_min,
            ingestion_status=ingestion_status,
            q=q, page=page, per_page=per_page, sort=sort,
        )
        return {"data": sources, "pagination": compute_pagination(total, page, per_page)}


@router.get("/{source_id}")
async def get_source(source_id: int):
    with get_db_session() as session:
        service = SourceService(session)
        source = service.get_source(source_id)
        if source is None:
            raise HTTPException(status_code=404, detail="Source not found")
        return {"data": source}


@extractions_router.get("/{extraction_id}")
async def get_extraction(extraction_id: int):
    with get_db_session() as session:
        service = SourceService(session)
        ext = service.get_extraction(extraction_id)
        if ext is None:
            raise HTTPException(status_code=404, detail="Extraction not found")
        return {"data": ext}
```

- [ ] **Step 5: Mount the extractions router in main.py**

Edit `/var/www/realms/realms/api/main.py`:

Find:
```python
from realms.api.routes import entities, classes, hierarchy, relationships, cultures, regions, sources, search, stats
```

Replace with:
```python
from realms.api.routes import entities, classes, hierarchy, relationships, cultures, regions, sources, search, stats
from realms.api.routes.sources import extractions_router
```

Then find:
```python
app.include_router(sources.router, prefix="/sources", tags=["sources"])
```

Add immediately below it:
```python
app.include_router(extractions_router, prefix="/extractions", tags=["extractions"])
```

- [ ] **Step 6: Run tests to verify pass**

```bash
cd /var/www/realms && pytest tests/test_sources.py -v
```

- [ ] **Step 7: Commit**

```bash
cd /var/www/realms && git add realms/services/source_service.py realms/api/routes/sources.py realms/api/main.py tests/test_sources.py && \
git commit -m "feat(realms): source + extraction service and routes"
```

---

## Task 14: Search Service + Route

**Files:**
- Create: `/var/www/realms/realms/services/search_service.py`
- Create: `/var/www/realms/tests/test_search.py`
- Modify: `/var/www/realms/realms/api/routes/search.py`

- [ ] **Step 1: Write failing tests**

Write `/var/www/realms/tests/test_search.py`:

```python
"""Integration tests for /search endpoints."""
import pytest

pytestmark = pytest.mark.integration


def test_global_search(client, seeded):
    response = client.get("/search/?q=Xapirip")
    assert response.status_code == 200
    data = response.json()["data"]
    assert any(e["name"] == "Xapiripë" for e in data["entities"])


def test_global_search_empty_query(client, seeded):
    response = client.get("/search/?q=")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["entities"] == []
    assert data["entity_classes"] == []
    assert data["cultures"] == []
    assert data["sources"] == []


def test_global_search_across_resources(client, seeded):
    response = client.get("/search/?q=Yanomami")
    assert response.status_code == 200
    data = response.json()["data"]
    assert any(c["name"] == "Yanomami" for c in data["cultures"])


def test_advanced_search_entity_filter(client, seeded):
    response = client.post("/search/advanced", json={
        "filters": {"entity_type": "plant_spirit", "realm": "forest"},
        "sort": "-consensus_confidence",
        "page": 1,
        "per_page": 20,
    })
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Chullachaqui"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /var/www/realms && pytest tests/test_search.py -q
```

- [ ] **Step 3: Implement `SearchService`**

Write `/var/www/realms/realms/services/search_service.py`:

```python
"""Service layer for global and advanced search."""
from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from realms.models import Culture, Entity, EntityClass, IngestionSource
from realms.services.class_service import _class_to_response
from realms.services.culture_service import _culture_to_response
from realms.services.entity_service import EntityService, _entity_to_summary
from realms.services.source_service import _source_to_response


class SearchService:
    def __init__(self, session: Session):
        self.session = session

    def global_search(self, q: str, limit: int = 20) -> dict[str, list[dict]]:
        if not q:
            return {"entities": [], "entity_classes": [], "cultures": [], "sources": []}
        like = f"%{q}%"
        entities = self.session.execute(
            select(Entity).where(or_(Entity.name.ilike(like), Entity.description.ilike(like))).limit(limit)
        ).scalars().all()
        classes = self.session.execute(
            select(EntityClass).where(or_(EntityClass.name.ilike(like), EntityClass.description.ilike(like))).limit(limit)
        ).scalars().all()
        cultures = self.session.execute(
            select(Culture).where(or_(Culture.name.ilike(like), Culture.description.ilike(like))).limit(limit)
        ).scalars().all()
        sources = self.session.execute(
            select(IngestionSource).where(IngestionSource.source_name.ilike(like)).limit(limit)
        ).scalars().all()
        return {
            "entities": [_entity_to_summary(e) for e in entities],
            "entity_classes": [_class_to_response(c) for c in classes],
            "cultures": [_culture_to_response(c) for c in cultures],
            "sources": [_source_to_response(s) for s in sources],
        }

    def advanced_entity_search(
        self,
        filters: dict[str, Any],
        sort: str = "-consensus_confidence",
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[dict], int]:
        svc = EntityService(self.session)
        return svc.list_entities(
            entity_type=filters.get("entity_type"),
            alignment=filters.get("alignment"),
            realm=filters.get("realm"),
            hierarchy_level_min=filters.get("hierarchy_level_min"),
            hierarchy_level_max=filters.get("hierarchy_level_max"),
            confidence_min=filters.get("confidence_min"),
            power=filters.get("power"),
            domain=filters.get("domain"),
            q=filters.get("q"),
            page=page,
            per_page=per_page,
            sort=sort,
        )
```

- [ ] **Step 4: Replace the search router**

Replace `/var/www/realms/realms/api/routes/search.py` with:

```python
"""Search API endpoints."""
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from realms.services.entity_service import compute_pagination
from realms.services.search_service import SearchService
from realms.utils.database import get_db_session

router = APIRouter()


class AdvancedSearchRequest(BaseModel):
    filters: dict[str, Any] = {}
    sort: str = "-consensus_confidence"
    page: int = 1
    per_page: int = 50


@router.get("/")
async def global_search(q: str = Query("")):
    with get_db_session() as session:
        service = SearchService(session)
        return {"data": service.global_search(q)}


@router.post("/advanced")
async def advanced_search(req: AdvancedSearchRequest):
    with get_db_session() as session:
        service = SearchService(session)
        entities, total = service.advanced_entity_search(
            filters=req.filters, sort=req.sort, page=req.page, per_page=req.per_page,
        )
        return {"data": entities, "pagination": compute_pagination(total, req.page, req.per_page)}
```

- [ ] **Step 5: Run tests to verify pass**

```bash
cd /var/www/realms && pytest tests/test_search.py -v
```

- [ ] **Step 6: Commit**

```bash
cd /var/www/realms && git add realms/services/search_service.py realms/api/routes/search.py tests/test_search.py && \
git commit -m "feat(realms): global and advanced search service"
```

---

## Task 15: Stats Service + Route

**Files:**
- Create: `/var/www/realms/realms/services/stats_service.py`
- Create: `/var/www/realms/tests/test_stats.py`
- Modify: `/var/www/realms/realms/api/routes/stats.py`

- [ ] **Step 1: Write failing tests**

Write `/var/www/realms/tests/test_stats.py`:

```python
"""Integration tests for /stats endpoint."""
import pytest

pytestmark = pytest.mark.integration


def test_stats_structure(client, seeded):
    response = client.get("/stats/")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_entities"] == 2
    assert data["by_type"]["plant_spirit"] == 1
    assert data["by_type"]["animal_ally"] == 1
    assert data["by_realm"]["forest"] == 2
    assert data["by_alignment"]["beneficial"] == 1
    assert data["by_alignment"]["neutral"] == 1
    assert data["sources_processed"] == 1
    assert data["total_extractions"] == 2
    assert 0.0 < data["avg_confidence"] <= 1.0


def test_stats_by_culture(client, seeded):
    response = client.get("/stats/")
    data = response.json()["data"]
    assert data["by_culture"]["Yanomami"] == 1
    assert data["by_culture"]["Shipibo-Konibo"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /var/www/realms && pytest tests/test_stats.py -q
```

- [ ] **Step 3: Implement `StatsService`**

Write `/var/www/realms/realms/services/stats_service.py`:

```python
"""Service layer for aggregate stats."""
from __future__ import annotations

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from realms.models import Entity, IngestedEntity, IngestionSource


class StatsService:
    def __init__(self, session: Session):
        self.session = session

    def get_stats(self) -> dict:
        total_entities = self.session.execute(select(func.count(Entity.id))).scalar_one() or 0
        by_type = dict(
            self.session.execute(
                select(Entity.entity_type, func.count(Entity.id))
                .where(Entity.entity_type.is_not(None))
                .group_by(Entity.entity_type)
            ).all()
        )
        by_realm = dict(
            self.session.execute(
                select(Entity.realm, func.count(Entity.id))
                .where(Entity.realm.is_not(None))
                .group_by(Entity.realm)
            ).all()
        )
        by_alignment = dict(
            self.session.execute(
                select(Entity.alignment, func.count(Entity.id))
                .where(Entity.alignment.is_not(None))
                .group_by(Entity.alignment)
            ).all()
        )

        # Cultures are stored as JSONB arrays; count in Python (fine for MVP scale)
        culture_counter: Counter[str] = Counter()
        for e in self.session.execute(select(Entity)).scalars().all():
            for name in (e.cultural_associations or []):
                culture_counter[name] += 1

        avg_conf = self.session.execute(select(func.avg(Entity.consensus_confidence))).scalar() or 0.0
        sources_processed = self.session.execute(
            select(func.count(IngestionSource.id)).where(IngestionSource.ingestion_status == "completed")
        ).scalar_one() or 0
        total_extractions = self.session.execute(select(func.count(IngestedEntity.id))).scalar_one() or 0
        last_updated = self.session.execute(select(func.max(Entity.updated_at))).scalar()

        return {
            "total_entities": total_entities,
            "by_type": by_type,
            "by_realm": by_realm,
            "by_alignment": by_alignment,
            "by_culture": dict(culture_counter),
            "avg_confidence": float(avg_conf),
            "sources_processed": sources_processed,
            "total_extractions": total_extractions,
            "last_updated": last_updated,
        }
```

- [ ] **Step 4: Replace the stats router**

Replace `/var/www/realms/realms/api/routes/stats.py` with:

```python
"""Statistics API endpoints."""
from fastapi import APIRouter

from realms.services.stats_service import StatsService
from realms.utils.database import get_db_session

router = APIRouter()


@router.get("/")
async def get_stats():
    with get_db_session() as session:
        service = StatsService(session)
        return {"data": service.get_stats()}
```

- [ ] **Step 5: Run tests to verify pass**

```bash
cd /var/www/realms && pytest tests/test_stats.py -v
```

- [ ] **Step 6: Commit**

```bash
cd /var/www/realms && git add realms/services/stats_service.py realms/api/routes/stats.py tests/test_stats.py && \
git commit -m "feat(realms): stats aggregation service"
```

---

## Task 16: Full Suite + Docker Smoke Test

**Files:**
- Modify: `/var/www/realms/realms/api/main.py` (dynamic timestamp)
- Create: `/var/www/realms/README.md`

- [ ] **Step 1: Fix the hardcoded timestamp in the health endpoint**

Edit `/var/www/realms/realms/api/main.py`.

Find:
```python
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "realms-api",
        "timestamp": "2026-04-18T10:00:00Z"  # Would be dynamic in real implementation
    }
```

Replace with:
```python
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    from datetime import datetime, timezone
    return {
        "status": "healthy",
        "service": "realms-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
```

- [ ] **Step 2: Run the full test suite**

```bash
cd /var/www/realms && pytest tests/ -v
```

Expected: all tests from Tasks 7–15 pass. Total ~40+ tests.

- [ ] **Step 3: Build the Docker image**

```bash
cd /var/www/realms && docker compose build realms-api
```

Expected: image builds without errors.

- [ ] **Step 4: Start the service**

```bash
cd /var/www/realms && docker compose -f /var/www/herbalist/docker-compose.yml -f /var/www/realms/docker-compose.yml up -d realms-api
```

Expected: container `realms-api` becomes healthy within 60 seconds.

- [ ] **Step 5: Smoke-test the live API**

Run:
```bash
curl -fsS http://127.0.0.1:8001/api/health
curl -fsS http://127.0.0.1:8001/entities/
curl -fsS http://127.0.0.1:8001/stats/
curl -fsS http://127.0.0.1:8001/docs | head -5
```

Expected output for health:
```json
{"status":"healthy","service":"realms-api","timestamp":"2026-04-18T..."}
```

Expected for `/entities/`: a JSON body with `data` (list) and `pagination` keys. Data may be empty if seed hasn't been run.

- [ ] **Step 6: Seed the live DB (one-time)**

```bash
docker compose exec realms-api python -m scripts.seed_realms
```

Expected: log line `Seed complete: {...}` showing 10 IDs.

Re-hit `/entities/` — should now return 2 entities.

- [ ] **Step 7: Write a minimal README**

Write `/var/www/realms/README.md`:

```markdown
# REALMS — Research Entity Archive for Light & Metaphysical Spirit Hierarchies

Read-only public API over a provenance-tracked knowledge base of spiritual
entities documented across global indigenous traditions.

## Docs

- `docs/PROJECT_OVERVIEW.md` — Vision and scope
- `docs/ARCHITECTURE.md` — System architecture
- `docs/DATA_MODEL.md` — PostgreSQL schema
- `docs/API_SPECS.md` — API specification
- `docs/plans/` — Implementation plans

## Quick Start

Extends the EstimaBio Docker stack. PostgreSQL, LiteLLM, and Neo4j are
expected to be running from the EstimaBio compose file.

```bash
# Start
docker compose \
  -f /var/www/herbalist/docker-compose.yml \
  -f /var/www/realms/docker-compose.yml \
  up -d realms-api

# Bootstrap schema + seed sample data (one-time)
docker compose exec realms-api python -m scripts.seed_realms

# Browse
open http://127.0.0.1:8001/docs
```

## Endpoints

Base URL: `http://127.0.0.1:8001`

| Path | Description |
|------|-------------|
| `/api/health` | Liveness probe |
| `/entities/` | List entities |
| `/entities/{id}` | Entity detail |
| `/entity-classes/` | List entity classes |
| `/hierarchy/tree` | Full nested hierarchy |
| `/hierarchy/flat` | Flattened hierarchy |
| `/relationships/` | Entity-to-entity relationships |
| `/cultures/` | Cultures |
| `/regions/` | Geographic regions |
| `/sources/` | Source documents |
| `/extractions/{id}` | Raw LLM extraction |
| `/search/?q=...` | Global search |
| `/search/advanced` | POST advanced search |
| `/stats/` | Aggregate counts |

Full spec: `docs/API_SPECS.md`.

## Testing

```bash
docker compose exec realms-api pytest tests/ -v
```

Tests hit a real PostgreSQL test database (`estimabio_test` by default).
No mocks — matches EstimaBio project convention.

## Status

**Phase 1 (MVP)** — Read-only API with seed data. This is what's built today.

**Not yet built (future plans):**
- Ingestion pipeline (LLM extractors for academic sources)
- Neo4j graph sync
- Web frontend (D3.js hierarchy, Cytoscape.js graph, Leaflet map)
- Alembic migrations (currently uses `create_all()` bootstrap)
- Rate limiting middleware
```

- [ ] **Step 8: Commit**

```bash
cd /var/www/realms && git add realms/api/main.py README.md && \
git commit -m "feat(realms): dynamic health timestamp + README + Phase 1 complete"
```

---

## Verification Summary

After completing all 16 tasks:

1. **Container boots:** `docker compose up -d realms-api` → healthy within 60s.
2. **Database bootstraps:** `bootstrap_realms_db` creates 9 tables idempotently.
3. **Seed populates:** `seed_realms` creates 2 entities, 2 cultures, 1 region, 1 source, 2 extractions, 1 relationship, 1 plant connection.
4. **API responds:** All endpoints in `docs/API_SPECS.md` (except ingestion-side) return correct shapes.
5. **Tests pass:** 40+ integration tests, all hitting a real PostgreSQL test DB.
6. **Docs updated:** `README.md` explains current state and what's next.

## Next Plans (Not in This Plan)

1. **REALMS Phase 2: Ingestion Pipeline** — Source discovery, LLM extraction workers, normalization/dedup, confidence scoring.
2. **REALMS Phase 3: Neo4j Sync** — Mirror entities and relationships into the existing Neo4j instance for graph traversal queries.
3. **REALMS Phase 4: Web Frontend** — D3.js hierarchy, Cytoscape.js relationship graph, Leaflet map, vanilla JS.
4. **REALMS Phase 5: Alembic Migrations** — Swap `create_all()` bootstrap for Alembic-managed schema versioning.
5. **REALMS Phase 6: Rate Limiting & Caching** — Slowapi middleware, Redis response cache, CDN headers.
