"""Infer weak relationships from same-chunk co-occurrence.

A co-occurrence edge is a weak signal — useful for bootstrapping the relationship
graph before LLM-based relationship extraction arrives. Each edge is created with
relationship_type='co_occurs_with' and strength='weak'.
"""
from __future__ import annotations

import logging
from itertools import combinations

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from realms.models import EntityRelationship

log = logging.getLogger(__name__)


def link_co_occurrences(
    session: Session,
    chunk_entity_ids: list[int],
    *,
    source_id: int,
    min_confidence: float = 0.5,
) -> int:
    """Upsert co-occurrence edges between every pair of entities in the same chunk.

    Symmetric: creates only one edge per unordered pair, always from lower to higher ID.
    Returns the number of edges created (not updated).
    """
    unique_ids = sorted(set(chunk_entity_ids))
    if len(unique_ids) < 2:
        return 0

    created = 0
    for a, b in combinations(unique_ids, 2):
        existing = session.execute(
            select(EntityRelationship).where(
                and_(
                    EntityRelationship.source_entity_id == a,
                    EntityRelationship.target_entity_id == b,
                    EntityRelationship.relationship_type == "co_occurs_with",
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            edge = EntityRelationship(
                source_entity_id=a,
                target_entity_id=b,
                relationship_type="co_occurs_with",
                description="Entities co-occurred in a source chunk during ingestion.",
                strength="weak",
                extraction_confidence=min_confidence,
                provenance_sources=[source_id],
            )
            session.add(edge)
            created += 1
        else:
            # Append the source to provenance
            srcs = list(existing.provenance_sources or [])
            if source_id not in srcs:
                srcs.append(source_id)
                existing.provenance_sources = srcs
                # Boost confidence slightly as more sources corroborate
                existing.extraction_confidence = min(
                    (existing.extraction_confidence or 0.0) + 0.05, 0.9
                )
                if len(srcs) >= 3:
                    existing.strength = "moderate"
    session.flush()
    return created
