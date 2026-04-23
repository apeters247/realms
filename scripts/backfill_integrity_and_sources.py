#!/usr/bin/env python3
"""Backfill integrity gate + Brave source discovery for low-confidence entities.

Step 1: Re-run integrity gate on entities with consensus_confidence = 0.4.
Step 2: Seed new pending ingestion_sources via Brave Search (requires BRAVE_API_KEY).

Usage:
    python scripts/backfill_integrity_and_sources.py [--dry-run] [--offset N] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from sqlalchemy import select

from realms.models import Entity, IngestedEntity, IngestionSource
from realms.utils.database import get_db_session
from realms.ingestion.integrity_gate import run_gate

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
BRAVE_KEY = os.getenv("BRAVE_API_KEY")

TRUSTED_DOMAINS = {
    "en.wikipedia.org": ("wikipedia", 0.80),
    "archive.org": ("archive_org", 0.75),
}
# Also accept *.edu and *.ac.uk
EDU_CRED = ("journal", 0.70)

# Confidence value stamped on early-ingestion entities
BACKFILL_CONFIDENCE = 0.4


def _is_trusted(url: str) -> tuple[str, float] | None:
    """Return (source_type, credibility_score) if URL is from a trusted domain."""
    for domain, meta in TRUSTED_DOMAINS.items():
        if domain in url:
            return meta
    if url.endswith(".edu") or ".edu/" in url or ".ac.uk" in url:
        return EDU_CRED
    return None


def _brave_search(entity_name: str, culture: str) -> list[dict]:
    """Call Brave Search API. Returns list of result dicts with url, title."""
    if not BRAVE_KEY:
        return []
    query = (
        f'"{entity_name}" {culture} mythology OR folklore OR spirit OR deity '
        f"site:en.wikipedia.org OR site:archive.org OR site:*.edu"
    )
    try:
        resp = requests.get(
            BRAVE_API_URL,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": BRAVE_KEY,
            },
            params={"q": query, "count": 5},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("web", {}).get("results", [])
    except Exception as exc:
        log.warning("Brave search failed for %r: %s", entity_name, exc)
        return []


def _primary_culture(entity: Entity) -> str:
    """Extract first cultural association string for search query."""
    assocs = entity.cultural_associations or []
    if isinstance(assocs, list) and assocs:
        return str(assocs[0])
    return ""


def _parse_extraction_ids(raw: object) -> list[int]:
    """Normalise extraction_instances to a list of ints.

    The JSONB column may be stored as a Python list (when loaded by SA), or
    occasionally as a JSON string if the column was written manually.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return [int(x) for x in raw if x is not None]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [int(x) for x in parsed if x is not None]
        except Exception:
            pass
    return []


def process_entity(
    session,
    entity: Entity,
    *,
    dry_run: bool,
    accept_threshold: float = 0.85,
    flag_threshold: float = 0.65,
) -> dict:
    """Process one entity: integrity re-check + Brave source seeding.

    Returns a summary dict with keys:
        entity_id, entity_name, integrity_action, brave_sources_added
    """
    result: dict = {
        "entity_id": entity.id,
        "entity_name": entity.name,
        "integrity_action": None,
        "brave_sources_added": 0,
    }

    # --- Step 1: Integrity re-check ---
    extraction_ids = _parse_extraction_ids(entity.extraction_instances)

    best_score = 0.0
    best_action = None

    for eid in extraction_ids[:5]:  # cap at 5 to limit LLM calls per entity
        ie = session.get(IngestedEntity, eid)
        if ie is None:
            continue
        ctx = ie.extraction_context or ""
        if not ctx:
            continue

        # Build extracted dict from IngestedEntity fields
        extracted: dict = {
            "name": ie.entity_name_raw or entity.name,
            "description": (
                ie.normalized_data.get("description")
                if isinstance(ie.normalized_data, dict)
                else None
            ),
            "quote_context": ie.quote_context or "",
        }

        gate_result = run_gate(
            extracted,
            ctx,
            accept_threshold=accept_threshold,
            flag_threshold=flag_threshold,
        )

        if gate_result.integrity_score > best_score:
            best_score = gate_result.integrity_score
            best_action = gate_result.action.value

        # Write integrity_meta back to the ingested_entity row
        if not dry_run:
            ie.integrity_meta = gate_result.to_jsonb()

    if best_score > 0 and best_score < flag_threshold:
        if not dry_run:
            entity.review_status = "flagged"
        result["integrity_action"] = "flagged"
        log.info(
            "Flagged entity %d %r (score=%.2f)", entity.id, entity.name, best_score
        )
    else:
        result["integrity_action"] = best_action or "skipped"

    # --- Step 2: Brave source discovery ---
    if BRAVE_KEY:
        culture = _primary_culture(entity)
        search_results = _brave_search(entity.name, culture)
        for hit in search_results:
            url = hit.get("url", "")
            title = hit.get("title", "") or f"{entity.name} (Brave discovery)"
            meta = _is_trusted(url)
            if meta is None:
                continue
            source_type, cred = meta

            # Check if this URL already exists in ingestion_sources
            existing = session.execute(
                select(IngestionSource).where(IngestionSource.url == url)  # url is the correct column name
            ).scalar_one_or_none()
            if existing is not None:
                continue

            if not dry_run:
                new_source = IngestionSource(
                    source_name=title,
                    source_type=source_type,
                    credibility_score=cred,
                    ingestion_status="pending",
                    url=url,
                    retrieval_method="brave_search",
                )
                session.add(new_source)
            result["brave_sources_added"] += 1
            log.debug("Seeded source: %s", url)

        time.sleep(1.0)  # Brave free tier: 1 req/sec

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without committing to the database",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Skip first N matching entities (default: 0)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process at most N entities; 0 means all (default: 0)",
    )
    args = parser.parse_args()

    if not BRAVE_KEY:
        log.warning(
            "BRAVE_API_KEY not set — skipping Brave source discovery (Step 2). "
            "Set the environment variable to enable source seeding."
        )

    query = (
        select(Entity)
        .where(Entity.consensus_confidence == BACKFILL_CONFIDENCE)
        .order_by(Entity.id)
    )
    if args.offset:
        query = query.offset(args.offset)
    if args.limit:
        query = query.limit(args.limit)

    processed = 0
    flagged = 0
    sources_added = 0

    with get_db_session() as session:
        entities = session.execute(query).scalars().all()
        total = len(entities)
        log.info(
            "Found %d entities with consensus_confidence=%.1f (offset=%d, limit=%d)",
            total,
            BACKFILL_CONFIDENCE,
            args.offset,
            args.limit or 0,
        )

        for entity in entities:
            result = process_entity(
                session,
                entity,
                dry_run=args.dry_run,
            )
            processed += 1
            if result["integrity_action"] == "flagged":
                flagged += 1
            sources_added += result["brave_sources_added"]

            if processed % 50 == 0:
                log.info("Progress: %d/%d processed", processed, total)
                if not args.dry_run:
                    session.commit()

        if not args.dry_run:
            session.commit()
            log.info("Committed all changes.")

    log.info(
        "Done. processed=%d flagged=%d brave_sources_added=%d dry_run=%s",
        processed,
        flagged,
        sources_added,
        args.dry_run,
    )


if __name__ == "__main__":
    main()
