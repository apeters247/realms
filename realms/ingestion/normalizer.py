"""Normalization: dedup by name+type, upsert into entities table."""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Iterable

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from realms.ingestion.extractor import ExtractedEntity
from realms.models import Entity, IngestedEntity

log = logging.getLogger(__name__)


def _normalize_name(name: str) -> str:
    """Lowercase + strip diacritics-tolerant whitespace; used only for matching."""
    s = name.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _strip_diacritics(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _stem_key(name: str) -> str:
    """Collapse trivial plural / diacritic differences for fuzzy matching.

    Example: 'Vodúns' and 'vodún' both map to 'vodun'.
    """
    s = _strip_diacritics(name.strip().lower())
    # Strip trailing plural-like suffix
    for suffix in ("es", "s"):
        if len(s) > 4 and s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    return re.sub(r"\s+", " ", s)


def _find_existing(session: Session, name: str) -> Entity | None:
    """Find an entity by exact name, case-insensitive, or fuzzy stem match."""
    # 1. exact case-insensitive
    hit = session.execute(
        select(Entity).where(Entity.name.ilike(name))
    ).scalar_one_or_none()
    if hit is not None:
        return hit

    # 2. stem equality across all entities (bounded N in MVP — Postgres trigram
    #    would be the production fix once count > ~10k)
    stem = _stem_key(name)
    candidates = session.execute(select(Entity)).scalars().all()
    for c in candidates:
        if _stem_key(c.name) == stem:
            log.info("Fuzzy match: %r ~= existing %r (stem=%s)", name, c.name, stem)
            return c
    return None


def _merge_list(existing: list | None, incoming: Iterable) -> list:
    result = list(existing or [])
    for item in incoming:
        if item and item not in result:
            result.append(item)
    return result


def _merge_alt_names(existing: dict | None, incoming: dict) -> dict:
    result = dict(existing or {})
    for lang, names in (incoming or {}).items():
        existing_list = result.get(lang, [])
        for name in names or []:
            if name and name not in existing_list:
                existing_list.append(name)
        if existing_list:
            result[lang] = existing_list
    return result


def upsert_entities(
    session: Session,
    extracted: list[ExtractedEntity],
    *,
    source_id: int,
    extraction_ids_by_name: dict[str, int],
) -> dict[str, int]:
    """Upsert extracted entities into the `entities` table.

    Returns a mapping of normalized name -> entity_id for all affected rows.
    """
    result: dict[str, int] = {}
    for ex in extracted:
        norm = _normalize_name(ex.name)
        candidate = _find_existing(session, ex.name)

        extraction_id = extraction_ids_by_name.get(norm)

        if candidate is None:
            entity = Entity(
                name=ex.name,
                entity_type=ex.entity_type,
                alignment=ex.alignment,
                realm=ex.realm,
                description=ex.description,
                alternate_names=dict(ex.alternate_names) if ex.alternate_names else None,
                powers=list(ex.powers) if ex.powers else None,
                domains=list(ex.domains) if ex.domains else None,
                cultural_associations=list(ex.cultural_associations) if ex.cultural_associations else None,
                geographical_associations=list(ex.geographical_associations) if ex.geographical_associations else None,
                provenance_sources=[source_id],
                extraction_instances=[extraction_id] if extraction_id is not None else [],
                consensus_confidence=ex.confidence,
                first_documented_year=ex.first_attested_year,
                evidence_period_start=ex.evidence_period_start,
                evidence_period_end=ex.evidence_period_end,
                historical_notes=ex.historical_notes,
            )
            session.add(entity)
            session.flush()
            log.info("Created entity: %s (id=%d, conf=%.2f)", ex.name, entity.id, ex.confidence)
            result[norm] = entity.id
        else:
            # Merge
            candidate.entity_type = candidate.entity_type or ex.entity_type
            candidate.alignment = candidate.alignment or ex.alignment
            candidate.realm = candidate.realm or ex.realm
            candidate.description = candidate.description or ex.description
            candidate.alternate_names = _merge_alt_names(candidate.alternate_names, ex.alternate_names)
            candidate.powers = _merge_list(candidate.powers, ex.powers)
            candidate.domains = _merge_list(candidate.domains, ex.domains)
            candidate.cultural_associations = _merge_list(candidate.cultural_associations, ex.cultural_associations)
            candidate.geographical_associations = _merge_list(candidate.geographical_associations, ex.geographical_associations)
            candidate.provenance_sources = _merge_list(candidate.provenance_sources, [source_id])
            if extraction_id is not None:
                candidate.extraction_instances = _merge_list(candidate.extraction_instances, [extraction_id])

            # Temporal merge: earliest wins, widest wins
            if ex.first_attested_year is not None:
                if (candidate.first_documented_year is None
                        or ex.first_attested_year < candidate.first_documented_year):
                    candidate.first_documented_year = ex.first_attested_year
            if ex.evidence_period_start is not None:
                if (candidate.evidence_period_start is None
                        or ex.evidence_period_start < candidate.evidence_period_start):
                    candidate.evidence_period_start = ex.evidence_period_start
            if ex.evidence_period_end is not None:
                if (candidate.evidence_period_end is None
                        or ex.evidence_period_end > candidate.evidence_period_end):
                    candidate.evidence_period_end = ex.evidence_period_end
            if ex.historical_notes and not candidate.historical_notes:
                candidate.historical_notes = ex.historical_notes

            # Recompute consensus_confidence from all linked extractions
            if candidate.extraction_instances:
                rows = session.execute(
                    select(IngestedEntity.extraction_confidence).where(
                        IngestedEntity.id.in_(candidate.extraction_instances)
                    )
                ).scalars().all()
                values = [v for v in rows if v is not None]
                if values:
                    candidate.consensus_confidence = sum(values) / len(values)
            log.info("Merged entity: %s (id=%d, conf=%.2f)", candidate.name, candidate.id, candidate.consensus_confidence or 0.0)
            result[norm] = candidate.id

    session.flush()
    return result
