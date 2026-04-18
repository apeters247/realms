"""Mirror REALMS entities and relationships from PostgreSQL into Neo4j.

Runs as a polling worker: reads entities updated since last sync, MERGEs
them + their relationships into the graph, then records progress.
"""
from __future__ import annotations

import logging
import os
import signal
import time
from datetime import datetime, timezone

from neo4j import GraphDatabase, Driver
from sqlalchemy import select
from sqlalchemy.orm import Session

from realms.models import Culture, Entity, EntityClass, EntityRelationship, GeographicRegion
from realms.utils.database import get_db_session

log = logging.getLogger("realms.neo4j_sync")

SYNC_INTERVAL = int(os.getenv("REALMS_SYNC_INTERVAL", "30"))
_shutdown = False


def _install_signal_handlers() -> None:
    def _handler(signum, _frame):
        global _shutdown
        log.info("Received signal %s, shutting down", signum)
        _shutdown = True

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


def _build_driver() -> Driver:
    uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "estimabio123")
    return GraphDatabase.driver(uri, auth=(user, password))


def _ensure_constraints(driver: Driver) -> None:
    """Create uniqueness constraints on each node type (idempotent)."""
    with driver.session() as s:
        for label in ("Entity", "EntityClass", "Culture", "Region"):
            s.run(
                f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.realms_id IS UNIQUE"
            )


def _sync_entities(driver: Driver, session: Session, since: datetime | None) -> int:
    """MERGE entities (and their class/culture/region links) updated after `since`."""
    stmt = select(Entity)
    if since is not None:
        stmt = stmt.where(Entity.updated_at > since)

    rows = session.execute(stmt).scalars().all()
    if not rows:
        return 0

    payloads = [
        {
            "realms_id": e.id,
            "name": e.name,
            "entity_type": e.entity_type,
            "alignment": e.alignment,
            "realm": e.realm,
            "hierarchy_level": e.hierarchy_level,
            "hierarchy_name": e.hierarchy_name,
            "consensus_confidence": e.consensus_confidence or 0.0,
            "description": e.description,
            "cultural_associations": list(e.cultural_associations or []),
            "geographical_associations": list(e.geographical_associations or []),
            "entity_class_id": e.entity_class_id,
        }
        for e in rows
    ]

    with driver.session() as s:
        s.run(
            """
            UNWIND $rows AS row
            MERGE (e:Entity {realms_id: row.realms_id})
            SET e.name = row.name,
                e.entity_type = row.entity_type,
                e.alignment = row.alignment,
                e.realm = row.realm,
                e.hierarchy_level = row.hierarchy_level,
                e.hierarchy_name = row.hierarchy_name,
                e.consensus_confidence = row.consensus_confidence,
                e.description = row.description
            WITH e, row
            FOREACH (culture_name IN row.cultural_associations |
                MERGE (c:Culture {name: culture_name})
                MERGE (e)-[:DOCUMENTED_BY]->(c)
            )
            FOREACH (region_name IN row.geographical_associations |
                MERGE (r:Region {name: region_name})
                MERGE (e)-[:FOUND_IN]->(r)
            )
            FOREACH (cid IN CASE WHEN row.entity_class_id IS NULL THEN [] ELSE [row.entity_class_id] END |
                MERGE (cl:EntityClass {realms_id: cid})
                MERGE (e)-[:INSTANCE_OF]->(cl)
            )
            """,
            rows=payloads,
        )
    return len(rows)


def _sync_classes(driver: Driver, session: Session) -> int:
    rows = session.execute(select(EntityClass)).scalars().all()
    if not rows:
        return 0
    payloads = [
        {
            "realms_id": c.id,
            "name": c.name,
            "hierarchy_level": c.hierarchy_level,
            "hierarchy_name": c.hierarchy_name,
            "description": c.description,
        }
        for c in rows
    ]
    with driver.session() as s:
        s.run(
            """
            UNWIND $rows AS row
            MERGE (c:EntityClass {realms_id: row.realms_id})
            SET c.name = row.name,
                c.hierarchy_level = row.hierarchy_level,
                c.hierarchy_name = row.hierarchy_name,
                c.description = row.description
            """,
            rows=payloads,
        )
    return len(rows)


def _sync_cultures(driver: Driver, session: Session) -> int:
    rows = session.execute(select(Culture)).scalars().all()
    if not rows:
        return 0
    payloads = [
        {
            "realms_id": c.id,
            "name": c.name,
            "region": c.region,
            "tradition_type": c.tradition_type,
            "language_family": c.language_family,
        }
        for c in rows
    ]
    with driver.session() as s:
        s.run(
            """
            UNWIND $rows AS row
            MERGE (c:Culture {name: row.name})
            SET c.realms_id = row.realms_id,
                c.region = row.region,
                c.tradition_type = row.tradition_type,
                c.language_family = row.language_family
            """,
            rows=payloads,
        )
    return len(rows)


def _sync_regions(driver: Driver, session: Session) -> int:
    rows = session.execute(select(GeographicRegion)).scalars().all()
    if not rows:
        return 0
    payloads = [
        {
            "realms_id": r.id,
            "name": r.name,
            "region_type": r.region_type,
            "center_latitude": r.center_latitude,
            "center_longitude": r.center_longitude,
        }
        for r in rows
    ]
    with driver.session() as s:
        s.run(
            """
            UNWIND $rows AS row
            MERGE (r:Region {name: row.name})
            SET r.realms_id = row.realms_id,
                r.region_type = row.region_type,
                r.center_latitude = row.center_latitude,
                r.center_longitude = row.center_longitude
            """,
            rows=payloads,
        )
    return len(rows)


def _sync_relationships(driver: Driver, session: Session, since: datetime | None) -> int:
    stmt = select(EntityRelationship)
    if since is not None:
        stmt = stmt.where(EntityRelationship.updated_at > since)
    rows = session.execute(stmt).scalars().all()
    if not rows:
        return 0

    # Group by relationship_type for clean Cypher
    by_type: dict[str, list[dict]] = {}
    for r in rows:
        by_type.setdefault(r.relationship_type, []).append({
            "source_id": r.source_entity_id,
            "target_id": r.target_entity_id,
            "description": r.description,
            "strength": r.strength,
            "confidence": r.extraction_confidence or 0.0,
        })

    with driver.session() as s:
        for rel_type, payload in by_type.items():
            rel_label = rel_type.upper().replace(" ", "_").replace("-", "_")[:50]
            s.run(
                f"""
                UNWIND $rows AS row
                MATCH (a:Entity {{realms_id: row.source_id}})
                MATCH (b:Entity {{realms_id: row.target_id}})
                MERGE (a)-[r:{rel_label}]->(b)
                SET r.description = row.description,
                    r.strength = row.strength,
                    r.confidence = row.confidence
                """,
                rows=payload,
            )
    return len(rows)


def run_once() -> dict:
    driver = _build_driver()
    try:
        _ensure_constraints(driver)
        with get_db_session() as session:
            # For MVP: full resync each pass. Incremental via `since` added below
            # once we track a checkpoint table.
            results = {
                "classes": _sync_classes(driver, session),
                "cultures": _sync_cultures(driver, session),
                "regions": _sync_regions(driver, session),
                "entities": _sync_entities(driver, session, since=None),
                "relationships": _sync_relationships(driver, session, since=None),
            }
        return results
    finally:
        driver.close()


def run_forever() -> int:
    _install_signal_handlers()
    log.info("REALMS Neo4j sync starting. interval=%ds", SYNC_INTERVAL)
    while not _shutdown:
        try:
            stats = run_once()
            log.info("Sync pass: %s", stats)
        except Exception as exc:  # noqa: BLE001
            log.exception("Sync error: %s", exc)
        for _ in range(SYNC_INTERVAL):
            if _shutdown:
                break
            time.sleep(1)
    log.info("REALMS Neo4j sync exiting cleanly")
    return 0
