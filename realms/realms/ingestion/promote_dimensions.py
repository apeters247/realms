"""Promote LLM-extracted culture + region names into first-class table rows.

Entity.cultural_associations and Entity.geographical_associations are populated
by the extractor as free-form JSONB arrays. This module reconciles those names
against the cultures / geographic_regions tables so /cultures/{id} and the map
view return complete data.

Idempotent: safe to re-run after every ingestion pass.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from realms.models import Culture, Entity, GeographicRegion

log = logging.getLogger(__name__)


@dataclass
class PromotionStats:
    cultures_added: int = 0
    cultures_already: int = 0
    regions_added: int = 0
    regions_already: int = 0


def _normalize(name: str) -> str:
    s = (name or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _collect_names(session: Session, field: str) -> Counter[str]:
    """Count how often each culture/region name appears across entities."""
    counter: Counter[str] = Counter()
    for e in session.execute(select(Entity)).scalars().all():
        vals = getattr(e, field) or []
        if not isinstance(vals, list):
            continue
        for v in vals:
            n = _normalize(v)
            if n:
                counter[n] += 1
    return counter


def promote_cultures(session: Session, min_count: int = 1) -> tuple[int, int]:
    """Insert Culture rows for every distinct cultural_associations value.

    Returns (added, already_present).
    """
    names = _collect_names(session, "cultural_associations")

    existing = {
        _normalize(c.name): c
        for c in session.execute(select(Culture)).scalars().all()
    }

    added = 0
    already = 0
    for name, count in names.items():
        if count < min_count:
            continue
        if name in existing:
            already += 1
            continue
        culture = Culture(
            name=name,
            description=f"Tradition referenced in {count} entity extraction(s); promoted from ingestion.",
        )
        session.add(culture)
        added += 1
        log.info("Promoted culture: %r (referenced by %d entities)", name, count)
    session.flush()
    return added, already


def promote_regions(session: Session, min_count: int = 1) -> tuple[int, int]:
    """Insert GeographicRegion rows for every distinct geographical_associations value."""
    names = _collect_names(session, "geographical_associations")

    existing = {
        _normalize(r.name): r
        for r in session.execute(select(GeographicRegion)).scalars().all()
    }

    added = 0
    already = 0
    for name, count in names.items():
        if count < min_count:
            continue
        if name in existing:
            already += 1
            continue
        region = GeographicRegion(
            name=name,
            region_type=None,
        )
        session.add(region)
        added += 1
        log.info("Promoted region: %r (referenced by %d entities)", name, count)
    session.flush()
    return added, already


def promote_all(session: Session) -> PromotionStats:
    stats = PromotionStats()
    stats.cultures_added, stats.cultures_already = promote_cultures(session)
    stats.regions_added, stats.regions_already = promote_regions(session)
    session.commit()
    return stats
