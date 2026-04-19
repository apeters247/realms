"""Long-running ingestion worker loop.

Polls `ingestion_sources` where `status='pending'`, processes one at a time.
Idempotent: rows transition pending -> processing -> completed/failed.
"""
from __future__ import annotations

import logging
import os
import signal
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from realms.ingestion.chunker import chunk_text
from realms.ingestion.extractor import PROMPT_VERSION, extract_entities
from realms.ingestion.fetcher import fetch_wikipedia
from realms.ingestion.normalizer import _normalize_name, upsert_entities
from realms.ingestion.promote_dimensions import promote_all
from realms.ingestion.relationships import link_co_occurrences
from realms.models import IngestedEntity, IngestionSource
from realms.utils.database import get_db_session

log = logging.getLogger("realms.ingestor")

POLL_INTERVAL = int(os.getenv("REALMS_INGESTOR_POLL_INTERVAL", "20"))
IDLE_SLEEP = int(os.getenv("REALMS_INGESTOR_IDLE_SLEEP", "60"))
MAX_CHUNKS_PER_SOURCE = int(os.getenv("REALMS_INGESTOR_MAX_CHUNKS", "20"))
STUCK_PROCESSING_MINUTES = int(os.getenv("REALMS_INGESTOR_STUCK_MINUTES", "30"))

_shutdown = False


def _reset_orphaned_sources(session: Session) -> int:
    """Reset 'processing' sources back to 'pending' if untouched for too long.

    Handles worker crashes / restarts where a source was claimed but never completed.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STUCK_PROCESSING_MINUTES)
    result = session.execute(
        update(IngestionSource)
        .where(IngestionSource.ingestion_status == "processing")
        .where(IngestionSource.updated_at < cutoff)
        .values(ingestion_status="pending", error_log=None)
    )
    session.commit()
    return result.rowcount or 0


def _install_signal_handlers() -> None:
    def _handler(signum, _frame):
        global _shutdown
        log.info("Received signal %s, shutting down after current source", signum)
        _shutdown = True

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


def _claim_next_source(session: Session) -> IngestionSource | None:
    """Atomically move one pending source to 'processing' and return it."""
    source = session.execute(
        select(IngestionSource)
        .where(IngestionSource.ingestion_status == "pending")
        .order_by(IngestionSource.id.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    ).scalar_one_or_none()
    if source is None:
        return None
    source.ingestion_status = "processing"
    session.commit()
    session.refresh(source)
    return source


def _process_source(session: Session, source: IngestionSource) -> tuple[int, int]:
    """Fetch -> chunk -> extract -> normalize. Returns (n_extractions, n_entities)."""
    assert source.url, "source.url is required"
    log.info("[source=%d] Fetching %s", source.id, source.url)
    fetched = fetch_wikipedia(source.url)

    source.raw_content_hash = fetched.content_hash
    source.storage_path = fetched.storage_path
    source.language = fetched.language
    session.flush()

    chunks = chunk_text(fetched.content_text)
    log.info("[source=%d] %d chunks", source.id, len(chunks))
    chunks = chunks[:MAX_CHUNKS_PER_SOURCE]

    n_extractions = 0
    all_extractions_by_norm: dict[str, int] = {}
    all_entities_by_norm: dict[str, list] = {}
    chunks_by_idx: dict[int, list[str]] = {}  # chunk_idx -> list of normalized entity names

    for i, chunk in enumerate(chunks):
        log.info("[source=%d] chunk %d/%d (%d chars, section=%s)",
                 source.id, i + 1, len(chunks), len(chunk.text), chunk.section_title)
        try:
            result = extract_entities(chunk.text, source_name=fetched.title)
        except Exception as exc:  # noqa: BLE001
            log.warning("[source=%d] extraction failed: %s", source.id, exc)
            continue

        chunk_names: list[str] = []
        for ent in result.entities:
            ingested = IngestedEntity(
                source_id=source.id,
                extraction_method="llm_prompt_v1",
                llm_model_used=result.model,
                llm_temperature=result.temperature,
                llm_prompt_version=PROMPT_VERSION,
                raw_extracted_data=asdict(ent),
                normalized_data=asdict(ent),
                entity_name_raw=ent.name,
                entity_name_normalized=ent.name.strip(),
                extraction_confidence=ent.confidence,
                extraction_context=chunk.text[:1500],
                section_title=chunk.section_title,
                quote_context=ent.quote_context,
                status="raw",
            )
            session.add(ingested)
            session.flush()
            n_extractions += 1
            norm = _normalize_name(ent.name)
            all_extractions_by_norm[norm] = ingested.id
            all_entities_by_norm.setdefault(norm, []).append(ent)
            chunk_names.append(norm)
        chunks_by_idx[i] = chunk_names

    # Upsert normalized entities (use the highest-confidence extraction per name)
    merged_entities = []
    for norm, extractions in all_entities_by_norm.items():
        best = max(extractions, key=lambda e: e.confidence)
        merged_entities.append(best)

    upserted = upsert_entities(
        session,
        merged_entities,
        source_id=source.id,
        extraction_ids_by_name=all_extractions_by_norm,
    )

    # Weak co-occurrence edges within each chunk
    n_edges = 0
    for chunk_names in chunks_by_idx.values():
        ids_in_chunk = [upserted[n] for n in chunk_names if n in upserted]
        n_edges += link_co_occurrences(session, ids_in_chunk, source_id=source.id)
    if n_edges:
        log.info("[source=%d] %d new co-occurrence edges", source.id, n_edges)

    # Promote newly-mentioned cultures / regions to first-class rows
    promo = promote_all(session)
    if promo.cultures_added or promo.regions_added:
        log.info("[source=%d] promoted cultures=+%d regions=+%d",
                 source.id, promo.cultures_added, promo.regions_added)

    session.commit()
    return n_extractions, len(upserted)


def run_once() -> bool:
    """Process one source. Returns True if a source was processed, False if none pending."""
    with get_db_session() as session:
        source = _claim_next_source(session)
        if source is None:
            return False

        try:
            n_ext, n_ent = _process_source(session, source)
            source.ingestion_status = "completed"
            source.processed_at = datetime.now(timezone.utc)
            source.error_log = None
            session.commit()
            log.info("[source=%d] COMPLETED extractions=%d entities=%d",
                     source.id, n_ext, n_ent)
            return True
        except Exception as exc:  # noqa: BLE001
            log.exception("[source=%d] FAILED: %s", source.id, exc)
            # Roll back any partial inserts from this source, then mark failed
            session.rollback()
            session.refresh(source)
            source.ingestion_status = "failed"
            source.error_log = str(exc)[:2000]
            source.processed_at = datetime.now(timezone.utc)
            session.commit()
            return True


def run_forever() -> int:
    _install_signal_handlers()
    log.info("REALMS ingestor starting. poll=%ds idle=%ds max_chunks=%d",
             POLL_INTERVAL, IDLE_SLEEP, MAX_CHUNKS_PER_SOURCE)
    with get_db_session() as session:
        reset_count = _reset_orphaned_sources(session)
        if reset_count:
            log.info("Reset %d orphaned 'processing' sources to pending", reset_count)
    while not _shutdown:
        processed = run_once()
        if not processed:
            log.debug("No pending sources, sleeping %ds", IDLE_SLEEP)
            _sleep_interruptible(IDLE_SLEEP)
        else:
            _sleep_interruptible(POLL_INTERVAL)
    log.info("REALMS ingestor exiting cleanly")
    return 0


def _sleep_interruptible(total_seconds: int) -> None:
    for _ in range(total_seconds):
        if _shutdown:
            return
        time.sleep(1)
