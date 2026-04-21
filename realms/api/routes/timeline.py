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


# ─── Gantt-lane endpoint ────────────────────────────────────────────────

# Static tradition-era map — used as fallback when per-entity temporal data
# is sparse. Keep in sync with web-next/src/islands/TimelineView.svelte.
TRADITION_ERAS: dict[str, tuple[int, int]] = {
    "sumerian": (-3000, -1700),
    "akkadian": (-2400, -550),
    "egyptian": (-3000, -30),
    "ancient egyptian": (-3000, -30),
    "greek": (-800, 400),
    "roman": (-500, 500),
    "etruscan": (-800, -100),
    "hittite": (-1600, -1200),
    "phoenician": (-1500, -300),
    "canaanite": (-2000, -500),
    "norse": (500, 1200),
    "celtic": (-400, 500),
    "irish": (0, 1500),
    "welsh": (400, 1500),
    "slavic": (500, 1500),
    "baltic": (800, 1500),
    "germanic": (0, 1000),
    "basque": (0, 2025),
    "christian": (30, 2025),
    "catholic": (100, 2025),
    "orthodox christian": (800, 2025),
    "coptic christian": (50, 2025),
    "hindu": (-1500, 2025),
    "vedic": (-1500, -500),
    "buddhist": (-500, 2025),
    "tibetan buddhist": (600, 2025),
    "jain": (-600, 2025),
    "taoist": (-500, 2025),
    "chinese": (-1200, 2025),
    "japanese": (500, 2025),
    "shinto": (500, 2025),
    "korean": (0, 2025),
    "siberian": (-2000, 2025),
    "mongol": (1000, 1800),
    "tengrism": (-200, 2025),
    "turkic": (500, 2025),
    "chukchi": (-500, 2025),
    "koryak": (-500, 2025),
    "nivkh": (0, 2025),
    "yup'ik": (0, 2025),
    "inuit": (0, 2025),
    "cherokee": (1000, 2025),
    "lakota": (1500, 2025),
    "navajo": (1400, 2025),
    "hopi": (1000, 2025),
    "plains indian": (1500, 2025),
    "aztec": (1300, 1521),
    "maya": (-1800, 1521),
    "inca": (1200, 1533),
    "yanomami": (0, 2025),
    "quechua": (1000, 2025),
    "yoruba": (800, 2025),
    "igbo": (1000, 2025),
    "akan": (1200, 2025),
    "vodou": (1700, 2025),
    "santería": (1500, 2025),
    "candomblé": (1700, 2025),
    "zulu": (1600, 2025),
    "san": (-10000, 2025),
    "fon": (1400, 2025),
    "polynesian": (500, 2025),
    "māori": (1200, 2025),
    "hawaiian": (1000, 2025),
    "aboriginal australian": (-50000, 2025),
    "persian": (-1000, 2025),
    "zoroastrian": (-1000, 2025),
    "hebrew": (-1200, 200),
    "jewish": (-1200, 2025),
    "islamic": (600, 2025),
    "arab": (-200, 2025),
    "pre-islamic arab": (-1000, 600),
}


@router.get("/lanes")
async def lanes(
    top_n: int = Query(25, ge=5, le=100,
                       description="Number of top-N traditions to include as lanes"),
    zoom: str = Query("century", pattern="^(millennium|century|decade)$"),
) -> dict:
    """Return tradition-by-century bucket counts, suitable for a Gantt view.

    Response shape:
        {
          "window": {"min_year": int, "max_year": int, "step": int},
          "lanes": [
            {
              "tradition": "Hindu",
              "start_year": -1500,
              "end_year": 2025,
              "n_entities": 866,
              "buckets": [{"year": -1500, "count": 12}, ...]
            },
            ...
          ]
        }
    """
    step_map = {"millennium": 1000, "century": 100, "decade": 10}
    step = step_map[zoom]

    with get_db_session() as session:
        rows = session.execute(
            select(
                Entity.id,
                Entity.name,
                Entity.cultural_associations,
                Entity.first_documented_year,
                Entity.evidence_period_start,
                Entity.evidence_period_end,
                Entity.consensus_confidence,
            ).where(Entity.cultural_associations.isnot(None))
        ).all()

    # First pass: count entities per tradition.
    tradition_totals: dict[str, int] = {}
    for r in rows:
        cultures = r.cultural_associations or []
        if not isinstance(cultures, list) or not cultures:
            continue
        primary = str(cultures[0])
        tradition_totals[primary] = tradition_totals.get(primary, 0) + 1

    top_traditions = [t for t, _ in sorted(
        tradition_totals.items(), key=lambda kv: -kv[1]
    )[:top_n]]

    # Second pass: build bucket counts per lane.
    lanes_out: list[dict] = []
    for t in top_traditions:
        norm_t = t.lower().strip()
        # Era fallback from static map.
        era_start, era_end = TRADITION_ERAS.get(norm_t, (0, 2025))

        bucket_counts: Counter = Counter()
        member_ids: list[int] = []
        for r in rows:
            cultures = r.cultural_associations or []
            if not isinstance(cultures, list) or not cultures or cultures[0] != t:
                continue
            member_ids.append(r.id)
            # Prefer per-entity year; fall back to tradition era start.
            y = r.first_documented_year if r.first_documented_year is not None else era_start
            bucket = (y // step) * step
            bucket_counts[bucket] += 1

        # Build buckets for the tradition's entire span at this zoom.
        buckets = [
            {"year": y, "count": bucket_counts.get(y, 0)}
            for y in range(
                (era_start // step) * step,
                (era_end // step) * step + step,
                step,
            )
            if bucket_counts.get(y, 0) > 0 or era_start <= y <= era_end
        ]

        lanes_out.append({
            "tradition": t,
            "start_year": era_start,
            "end_year": era_end,
            "n_entities": tradition_totals[t],
            "buckets": buckets,
        })

    # Compute overall window.
    all_starts = [l["start_year"] for l in lanes_out]
    all_ends = [l["end_year"] for l in lanes_out]
    win_min = min(all_starts) if all_starts else -3000
    win_max = max(all_ends) if all_ends else 2025

    return {"data": {
        "window": {"min_year": win_min, "max_year": win_max, "step": step, "zoom": zoom},
        "lanes": lanes_out,
    }}


@router.get("/bucket_members")
async def bucket_members(
    tradition: str = Query(..., description="Tradition name"),
    start_year: int = Query(...),
    end_year: int = Query(...),
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    """List entities in a specific tradition × year-range bucket.

    Used by the Gantt UI's drill-in panel.
    """
    with get_db_session() as session:
        stmt = (
            select(Entity)
            .where(Entity.cultural_associations.isnot(None))
            .where(Entity.review_status != "merged")
            .order_by(Entity.consensus_confidence.desc().nulls_last())
        )
        rows = session.execute(stmt).scalars().all()

    matches: list[dict] = []
    for e in rows:
        cultures = e.cultural_associations or []
        if not isinstance(cultures, list) or not cultures or cultures[0] != tradition:
            continue
        y = e.first_documented_year
        if y is None:
            # Accept by tradition-era fallback.
            norm_t = tradition.lower().strip()
            era = TRADITION_ERAS.get(norm_t)
            if era is None or era[0] > end_year or era[1] < start_year:
                continue
        else:
            if not (start_year <= y <= end_year):
                continue
        matches.append({
            "id": e.id,
            "name": e.name,
            "entity_type": e.entity_type,
            "alignment": e.alignment,
            "first_documented_year": e.first_documented_year,
            "consensus_confidence": float(e.consensus_confidence or 0),
        })
        if len(matches) >= limit:
            break
    return {"data": {
        "tradition": tradition,
        "start_year": start_year,
        "end_year": end_year,
        "members": matches,
        "count": len(matches),
    }}
