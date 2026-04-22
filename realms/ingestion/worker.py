"""Long-running ingestion worker loop.

Polls `ingestion_sources` where `status='pending'`, processes one at a time.
Idempotent: rows transition pending -> processing -> completed/failed.
"""
from __future__ import annotations

import logging
import os
import re
import signal
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, select, update
from sqlalchemy.orm import Session

from realms.ingestion.archive_fetcher import fetch_archive
from realms.ingestion.chunker import chunk_text
from realms.ingestion.extractor import PROMPT_VERSION, ROLE_FIELDS, extract_entities
from realms.ingestion.fetcher import FetchedDocument, fetch_html, fetch_wikipedia, fetch_wikisource
from realms.ingestion.integrity_gate import Action, run_gate
from realms.ingestion.normalizer import _find_existing, _normalize_name, upsert_entities
from realms.ingestion.promote_dimensions import promote_all
from realms.ingestion.pubmed_fetcher import fetch_pubmed
from realms.ingestion.relationships import link_co_occurrences, upsert_role_edges
from realms.models import IngestedEntity, IngestionSource
from realms.utils.database import get_db_session

log = logging.getLogger("realms.ingestor")

POLL_INTERVAL = int(os.getenv("REALMS_INGESTOR_POLL_INTERVAL", "20"))
IDLE_SLEEP = int(os.getenv("REALMS_INGESTOR_IDLE_SLEEP", "60"))
MAX_CHUNKS_PER_SOURCE = int(os.getenv("REALMS_INGESTOR_MAX_CHUNKS", "8"))
STUCK_PROCESSING_MINUTES = int(os.getenv("REALMS_INGESTOR_STUCK_MINUTES", "30"))
# Parallel extraction — each source's chunks fan out to this many concurrent
# LLM calls. 4 is a safe default that keeps us well under OpenRouter's rate
# limits while 3-4x-ing end-to-end throughput per source.
CHUNK_CONCURRENCY = int(os.getenv("REALMS_INGESTOR_CHUNK_CONCURRENCY", "4"))
CANONICALIZE_EVERY_N = int(os.getenv("REALMS_CANONICALIZE_EVERY_N", "20"))
_sources_since_canon = 0
# Stream I: integrity gate. Disabled by default until extractor v4 verbatim quotes
# are confirmed in production. Set REALMS_INTEGRITY_GATE=on to enable.
INTEGRITY_GATE_ENABLED = os.getenv("REALMS_INTEGRITY_GATE", "off").lower() in {"on", "1", "true"}
INTEGRITY_ACCEPT_THRESHOLD = float(os.getenv("REALMS_INTEGRITY_ACCEPT", "0.99"))
INTEGRITY_FLAG_THRESHOLD = float(os.getenv("REALMS_INTEGRITY_FLAG", "0.90"))

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
    """Atomically move one pending source to 'processing' and return it.

    Priority policy:
      1. source_type rank (encyclopedia > wikipedia > primary_source > journal > other).
         Journals go last because many URLs are paywalled landing pages or
         PDF redirects that fail fetch; we pick them up only after the
         reliably-fetchable sources drain.
      2. credibility_score desc as a tiebreaker.
      3. id asc as the final deterministic tiebreaker.
    """
    type_rank = case(
        (IngestionSource.source_type == "encyclopedia", 1),
        (IngestionSource.source_type == "wikipedia", 2),
        (IngestionSource.source_type == "archive_org", 3),
        (IngestionSource.source_type == "primary_source", 4),
        (IngestionSource.source_type == "book", 5),
        (IngestionSource.source_type == "pubmed", 6),
        (IngestionSource.source_type == "journal", 7),
        else_=8,
    )
    source = session.execute(
        select(IngestionSource)
        .where(IngestionSource.ingestion_status == "pending")
        .order_by(
            type_rank.asc(),
            IngestionSource.credibility_score.desc().nulls_last(),
            IngestionSource.id.asc(),
        )
        .limit(1)
        .with_for_update(skip_locked=True)
    ).scalar_one_or_none()
    if source is None:
        return None
    source.ingestion_status = "processing"
    session.commit()
    session.refresh(source)
    return source


def _dispatch_fetch(source: IngestionSource) -> FetchedDocument:
    """Route the fetch call by source_type + URL host.

    - ``pubmed`` → NCBI E-utilities
    - ``archive_org`` / ``archive.org`` → Internet Archive scholar fetcher
    - ``wikipedia`` (or legacy unknown) with wikipedia.org URL → MediaWiki extract
    - ``encyclopedia`` with wikisource.org URL → Wikisource extract
    - Any other HTTP(S) URL → generic HTML fetcher (theoi, perseus, journal
      landing pages, newadvent, archive.org non-details, etc.)
    """
    stype = (source.source_type or "wikipedia").lower()
    url = source.url or ""
    host = url.split("/", 3)[2].lower() if "://" in url else ""

    if stype == "pubmed":
        return fetch_pubmed(url)
    if stype in ("archive_org", "archive.org", "archive"):
        return fetch_archive(url)

    # Host-based routing catches Wikisource-hosted encyclopedias regardless
    # of how they were typed at seed time.
    if "wikisource.org" in host:
        return fetch_wikisource(url)
    if "wikipedia.org" in host:
        return fetch_wikipedia(url)

    # Journal / primary_source / anything else with an HTTP URL.
    if url.startswith(("http://", "https://")):
        # Skip binary formats we can't parse. Detect from extension OR from
        # path tokens (many journal landing pages live at .../pdf/<id>).
        lower = url.lower().split("?", 1)[0]
        if (lower.endswith((".pdf", ".epub", ".mobi", ".djvu", ".ps", ".gz", ".zip"))
                or "/pdf/" in lower
                or "/download" in lower
                or "/fulltext" in lower):
            raise RuntimeError(
                f"binary / PDF-only endpoint, skipping {url}"
            )
        return fetch_html(url)

    # Legacy fallback — the old behaviour.
    return fetch_wikipedia(url)


# High-signal religion/mythology keywords. Kept short and specific so
# that general-interest Britannica articles (biography, geography,
# botany, politics, physics, …) don't slip through. Words like
# "tradition" and "sacred" are too generic — they can appear in any
# humanities prose — so they're excluded.
_REL_KEYWORDS = {
    "god ", "gods ", "goddess", "deity", "deities", "divine",
    "pantheon", "mythology", "mythological",
    " myth ", " myths ", "mythic",
    " cult ", " cults ", "cultic",
    "worship", "worshipped", "worshiped", "worshipper",
    "temple", "shrine", "sanctuary",
    "oracle", "prophet", "prophecy",
    "priest", "priestess", "shaman", "druid",
    "demon", "demonic",
    " angel ", " angels ", "archangel",
    " saint ", " saints ", "canonization", "beatified",
    "messiah", "avatar", "incarnation", "manifestation",
    "apparition", "our lady",
    "spirit of", "spirit-being", "ancestral spirit", "nature spirit",
    "water spirit", "forest spirit", "tutelary",
    "monster", "cryptid", "legendary creature", "mythic beast",
    "folklore", "folktale",
    "underworld", "afterlife", " heaven", " hell",
    "animism", "animist", "totem",
    "divination", "sorcery", "witchcraft",
    "psychopomp", "thunder god", "sea god",
    "nymph", "faun", "satyr", "dragon", "titan", "djinn", "jinn", "ghoul",
    "orisha", "kami", "yaksha", "bodhisattva", "loa",
    "syncretism", "syncretized", "pagan", "paganism",
}

# Title patterns that indicate biographical (non-entity) Britannica articles.
# Example: "Airey, Richard Airey", "Ainger, Alfred", "Aimard, Gustave".
# A surname-first comma pattern with an ordinary given name = biography,
# unless the name is clearly saintly ("Saint X" or "Our Lady of Y").
_BIOGRAPHICAL_TITLE_RE = re.compile(
    r"^[A-Z][a-zA-Zàâäéèêëîïôöùûüç'-]{2,},\s+[A-Z]",
)

def _looks_biographical(title: str) -> bool:
    if not title:
        return False
    # Strip encyclopedia suffix from seed names like "Airey (Britannica, 1911)".
    t = re.sub(r"\s*\([^)]+(Encyclopedia|Encyclopædia|Dictionary)[^)]*\)\s*$",
               "", title)
    if not _BIOGRAPHICAL_TITLE_RE.match(t):
        return False
    # Allow hagiography through.
    lower = t.lower()
    if any(tok in lower for tok in ("saint ", "st.", "blessed ", "holy ",
                                     "our lady", "virgin mary", "pope ")):
        return False
    return True


def _is_out_of_scope(title: str, text: str) -> bool:
    """Quick relevance heuristic to skip non-entity Britannica/Wikisource pages.

    Two-pass check:
      1. Title pattern — biographical "Lastname, Firstname" titles skip
         unless the name is clearly religious.
      2. Keyword sniff — the first ~3000 chars must contain at least one
         high-signal religion/mythology keyword.
    """
    if not text:
        return True
    if _looks_biographical(title):
        return True
    # Only gate substantial pages. Tiny stub pages fall through and let
    # the LLM decide — cheaply.
    if len(text) < 400:
        return False
    sample = text[:3000].lower()
    title_l = (title or "").lower()
    haystack = " " + title_l + " " + sample + " "
    for kw in _REL_KEYWORDS:
        if kw in haystack:
            return False
    return True


def _process_source(session: Session, source: IngestionSource) -> tuple[int, int]:
    """Fetch -> chunk -> extract -> normalize. Returns (n_extractions, n_entities)."""
    if not source.url:
        raise RuntimeError(
            f"source {source.id} has no URL — book/manual seeds are not auto-ingestable"
        )
    log.info("[source=%d type=%s] Fetching %s", source.id, source.source_type, source.url)
    fetched = _dispatch_fetch(source)

    source.raw_content_hash = fetched.content_hash
    source.storage_path = fetched.storage_path
    source.language = fetched.language
    session.flush()

    # Relevance pre-filter. Many scholarly-encyclopedia seeds (Britannica
    # 1911 "Aidin", "Ailanthus", biography articles) have no entity content.
    # Skip LLM cost for them by scanning for at least one religion/mythology
    # keyword in the fetched text.
    if _is_out_of_scope(fetched.title, fetched.content_text):
        log.info(
            "[source=%d] skipped — no religion/mythology keywords in text (title=%r)",
            source.id, fetched.title,
        )
        return (0, 0)

    chunks = chunk_text(fetched.content_text)
    log.info("[source=%d] %d chunks", source.id, len(chunks))
    chunks = chunks[:MAX_CHUNKS_PER_SOURCE]

    n_extractions = 0
    all_extractions_by_norm: dict[str, int] = {}
    all_entities_by_norm: dict[str, list] = {}
    chunks_by_idx: dict[int, list[str]] = {}  # chunk_idx -> list of normalized entity names

    # Parallel extraction: fan out up to CHUNK_CONCURRENCY LLM calls at once.
    # The extractor is blocking (requests), so we use a ThreadPoolExecutor.
    from concurrent.futures import ThreadPoolExecutor

    def _extract_one(i_and_chunk):
        i, chunk = i_and_chunk
        try:
            return i, chunk, extract_entities(chunk.text, source_name=fetched.title)
        except Exception as exc:  # noqa: BLE001
            log.warning("[source=%d] chunk %d extraction failed: %s", source.id, i + 1, exc)
            return i, chunk, None

    chunk_results = []
    with ThreadPoolExecutor(max_workers=CHUNK_CONCURRENCY) as pool:
        chunk_results = list(pool.map(_extract_one, list(enumerate(chunks))))
    # Preserve the original order for deterministic logging.
    chunk_results.sort(key=lambda t: t[0])

    for i, chunk, result in chunk_results:
        if result is None:
            continue
        log.info("[source=%d] chunk %d/%d (%d chars, section=%s) → %d ents",
                 source.id, i + 1, len(chunks), len(chunk.text), chunk.section_title,
                 len(result.entities))

        chunk_names: list[str] = []
        for ent in result.entities:
            # Stream I: integrity gate.
            integrity_meta = None
            integrity_status = "raw"
            if INTEGRITY_GATE_ENABLED:
                try:
                    verdict = run_gate(
                        asdict(ent),
                        chunk.text,
                        accept_threshold=INTEGRITY_ACCEPT_THRESHOLD,
                        flag_threshold=INTEGRITY_FLAG_THRESHOLD,
                    )
                    integrity_meta = verdict.to_jsonb()
                    if verdict.action == Action.REJECT:
                        log.info("[source=%d] REJECT %s (score=%.2f)",
                                 source.id, ent.name, verdict.integrity_score)
                        continue  # skip persistence entirely
                    if verdict.action == Action.FLAG_FOR_REVIEW:
                        integrity_status = "flagged"
                        log.info("[source=%d] FLAG %s (score=%.2f)",
                                 source.id, ent.name, verdict.integrity_score)
                except Exception as exc:  # noqa: BLE001
                    log.warning("[source=%d] integrity gate error on %s: %s",
                                source.id, ent.name, exc)
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
                integrity_meta=integrity_meta,
                status=integrity_status,
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

    # v3: explicit role claims -> typed edges. Creates stub entities for
    # unknown targets so the graph continues to grow; the stub is filled in
    # later if/when its own source is ingested.
    def _resolve(n: str) -> int | None:
        norm = _normalize_name(n)
        if norm in upserted:
            return upserted[norm]
        existing = _find_existing(session, n)
        if existing is not None:
            return existing.id
        name = n.strip()
        if len(name) < 2 or len(name) > 200:
            return None
        # Create a low-confidence stub
        from realms.models import Entity as _Entity  # local to avoid top-level cycle
        stub = _Entity(
            name=name,
            provenance_sources=[source.id],
            consensus_confidence=0.4,
            description=(
                f"Stub entity — referenced by another entity from source #{source.id} "
                f"but not yet directly extracted from its own source."
            ),
        )
        session.add(stub)
        session.flush()
        log.info("[source=%d] stub created: %r (id=%d)", source.id, name, stub.id)
        upserted[norm] = stub.id
        return stub.id

    n_role_edges = 0
    for ex in merged_entities:
        if not ex.roles:
            continue
        subject_id = upserted.get(_normalize_name(ex.name))
        if subject_id is None:
            continue
        n_role_edges += upsert_role_edges(
            session, subject_id, ex.roles,
            source_id=source.id, resolver=_resolve,
            confidence=min(0.85, max(0.7, ex.confidence)),
        )
    if n_role_edges:
        log.info("[source=%d] %d role-based typed edges", source.id, n_role_edges)

    # Promote newly-mentioned cultures / regions to first-class rows
    promo = promote_all(session)
    if promo.cultures_added or promo.regions_added:
        log.info("[source=%d] promoted cultures=+%d regions=+%d",
                 source.id, promo.cultures_added, promo.regions_added)

    # Continuous canonicalization. Every 20 processed sources, re-apply
    # the tradition canonical-form map so newly-extracted tag variants
    # (Christianity / Christian, Hinduism / Hindu, Egyptian / Ancient
    # Egyptian, …) don't accumulate. Cheap: touches only the entities
    # whose cultural_associations changed in the most recent batch.
    global _sources_since_canon
    _sources_since_canon += 1
    if _sources_since_canon >= CANONICALIZE_EVERY_N:
        _sources_since_canon = 0
        try:
            from scripts.canonicalize_traditions import canonicalise_one, dedupe_preserving_order
            from realms.models import Entity
            from sqlalchemy import select as _select
            # upserted is a dict: normalised_name → entity_id (int). Touch
            # only the entities just upserted in this source.
            ent_ids = list(upserted.values())
            if ent_ids:
                touched = 0
                for e in session.execute(
                    _select(Entity).where(Entity.id.in_(ent_ids))
                ).scalars():
                    ca = e.cultural_associations or []
                    if not isinstance(ca, list):
                        continue
                    new = dedupe_preserving_order([canonicalise_one(x) for x in ca])
                    if new != ca:
                        e.cultural_associations = new
                        touched += 1
                if touched:
                    log.info("[source=%d] canonicalised cultures on %d entities",
                             source.id, touched)
                    session.commit()
        except Exception as exc:  # noqa: BLE001
            log.warning("[source=%d] canonicalize hook error: %s", source.id, exc)

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
