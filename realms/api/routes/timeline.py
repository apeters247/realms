"""Phase 5 — temporal view of entities.

Answers 'when' questions: which entities were first attested between year X and
year Y; how first_documented_year distributes by century.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import and_, or_, select

from realms.models import Entity
from realms.utils.database import get_db_session

router = APIRouter()


def _ordinal(n: int) -> str:
    """Return the English ordinal suffix for ``n`` (1→'1st', 2→'2nd', 11→'11th')."""
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def _century_bucket(year: int) -> str:
    """Return a human label for the century of ``year``. BCE → negative labels."""
    if year >= 0:
        c = (year // 100) + 1
        return f"{_ordinal(c)} century CE"
    else:
        c = (abs(year) // 100) + 1
        return f"{_ordinal(c)} century BCE"


@router.get("/entities")
async def entities_in_window(
    start_year: int | None = Query(None, description="Inclusive lower bound (CE)"),
    end_year: int | None = Query(None, description="Inclusive upper bound (CE)"),
    culture: str | None = Query(None, description="Filter by cultural association substring"),
    limit: int = Query(200, ge=1, le=1000),
) -> dict[str, Any]:
    """Entities whose evidence_period overlaps [start_year, end_year].

    An entity matches if any of the following overlap the window:
      - first_documented_year
      - [evidence_period_start, evidence_period_end]
    """
    with get_db_session() as session:
        stmt = select(Entity)

        if start_year is not None and end_year is not None:
            # Overlap semantics: period overlaps window if start<=end and end>=start.
            period_overlap = and_(
                Entity.evidence_period_start.is_not(None),
                Entity.evidence_period_end.is_not(None),
                Entity.evidence_period_start <= end_year,
                Entity.evidence_period_end >= start_year,
            )
            point_in_window = and_(
                Entity.first_documented_year.is_not(None),
                Entity.first_documented_year >= start_year,
                Entity.first_documented_year <= end_year,
            )
            stmt = stmt.where(or_(period_overlap, point_in_window))
        elif start_year is not None:
            stmt = stmt.where(or_(
                Entity.first_documented_year >= start_year,
                Entity.evidence_period_end >= start_year,
            ))
        elif end_year is not None:
            stmt = stmt.where(or_(
                Entity.first_documented_year <= end_year,
                Entity.evidence_period_start <= end_year,
            ))
        else:
            # No window → require at least first_documented_year to be set
            stmt = stmt.where(Entity.first_documented_year.is_not(None))

        stmt = stmt.order_by(Entity.first_documented_year.asc().nullslast(), Entity.id.asc()).limit(limit)
        rows = list(session.execute(stmt).scalars().all())

        if culture:
            needle = culture.lower()
            rows = [r for r in rows if any(
                needle in str(c).lower() for c in (r.cultural_associations or [])
            )]

        return {"data": [
            {
                "id": r.id,
                "name": r.name,
                "entity_type": r.entity_type,
                "first_documented_year": r.first_documented_year,
                "evidence_period_start": r.evidence_period_start,
                "evidence_period_end": r.evidence_period_end,
                "historical_notes": r.historical_notes,
                "cultural_associations": r.cultural_associations or [],
            }
            for r in rows
        ]}


@router.get("/summary")
async def timeline_summary() -> dict[str, Any]:
    """Histogram of first_documented_year by century."""
    with get_db_session() as session:
        years = session.execute(
            select(Entity.first_documented_year).where(Entity.first_documented_year.is_not(None))
        ).scalars().all()
        counts = Counter(_century_bucket(y) for y in years)
        # Return buckets in chronological order
        def _century_sort_key(label: str) -> int:
            import re
            m = re.match(r"(\d+)", label)
            n = int(m.group(1)) if m else 0
            return -n if "BCE" in label else n
        ordered = sorted(counts.items(), key=lambda kv: _century_sort_key(kv[0]))
        return {"data": {
            "total_dated": len(years),
            "buckets": [{"century": c, "count": n} for c, n in ordered],
        }}
