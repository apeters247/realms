"""Infer weak relationships from same-chunk co-occurrence + promote explicit role claims.

- `link_co_occurrences`: every pair of entities extracted from the same chunk gets a
  weak `co_occurs_with` edge (bootstrap signal before classification).
- `upsert_role_edges`: role fields emitted by extractor v3 (parents, children,
  consorts, etc.) become strong typed edges directly, bypassing co-occurrence.
"""
from __future__ import annotations

import logging
from itertools import combinations

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from realms.ingestion.extractor import ROLE_FIELDS
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


def upsert_role_edges(
    session: Session,
    subject_id: int,
    roles: dict[str, list[str]],
    *,
    source_id: int,
    resolver,
    confidence: float = 0.85,
) -> int:
    """Promote role-field claims into typed relationship edges.

    ``resolver(name)`` returns the entity ID for a given name (or None if missing
    from our DB — in which case the role claim is dropped). It should typically
    wrap :func:`normalizer._find_existing`.

    Each role in ``roles`` maps to a (relationship_type, reverse) tuple from
    :data:`extractor.ROLE_FIELDS`. If ``reverse=True`` the edge goes from the
    named target back to ``subject_id`` (e.g., ``parents`` ⇒ target is the parent).
    """
    created = 0
    for field, names in roles.items():
        if field not in ROLE_FIELDS:
            continue
        rel_type, reverse = ROLE_FIELDS[field]
        for name in names or []:
            target_id = resolver(name)
            if target_id is None or target_id == subject_id:
                continue
            if reverse:
                src_id, tgt_id = target_id, subject_id
            else:
                src_id, tgt_id = subject_id, target_id

            existing = session.execute(
                select(EntityRelationship).where(and_(
                    EntityRelationship.source_entity_id == src_id,
                    EntityRelationship.target_entity_id == tgt_id,
                    EntityRelationship.relationship_type == rel_type,
                ))
            ).scalar_one_or_none()
            if existing is None:
                # Upgrade an existing co_occurs_with between the same nodes if present
                co_occ = session.execute(
                    select(EntityRelationship).where(and_(
                        EntityRelationship.source_entity_id == min(src_id, tgt_id),
                        EntityRelationship.target_entity_id == max(src_id, tgt_id),
                        EntityRelationship.relationship_type == "co_occurs_with",
                    ))
                ).scalar_one_or_none()
                if co_occ is not None:
                    co_occ.relationship_type = rel_type
                    co_occ.source_entity_id = src_id
                    co_occ.target_entity_id = tgt_id
                    co_occ.strength = "strong"
                    co_occ.extraction_confidence = max(
                        co_occ.extraction_confidence or 0.0, confidence
                    )
                    srcs = list(co_occ.provenance_sources or [])
                    if source_id not in srcs:
                        srcs.append(source_id)
                        co_occ.provenance_sources = srcs
                    created += 1
                    continue

                edge = EntityRelationship(
                    source_entity_id=src_id,
                    target_entity_id=tgt_id,
                    relationship_type=rel_type,
                    description=f"Extracted from source #{source_id} ({field} role claim).",
                    strength="strong",
                    extraction_confidence=confidence,
                    provenance_sources=[source_id],
                )
                session.add(edge)
                created += 1
            else:
                srcs = list(existing.provenance_sources or [])
                if source_id not in srcs:
                    srcs.append(source_id)
                    existing.provenance_sources = srcs
                existing.extraction_confidence = min(
                    max(existing.extraction_confidence or 0.0, confidence) + 0.02, 0.95
                )
                if len(srcs) >= 2:
                    existing.strength = "strong"
    session.flush()
    return created
