"""Stream I — public integrity metrics.

Surfaces the corpus-level integrity score measured nightly by the oracle
sampler. Also returns per-extraction integrity metadata for
``/integrity/entity/{id}`` so the researcher UI can display verification
trails.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import and_, desc, func, select

from realms.models import IngestedEntity, IntegrityAudit
from realms.utils.database import get_db_session

router = APIRouter()


@router.get("/stats")
async def integrity_stats(days: int = Query(30, ge=1, le=365)):
    """30-day rolling integrity metrics.

    Returns:
        - ``corpus_error_rate``: aggregate contradicted / sampled over window.
        - ``last_audit_at``: most recent oracle sampler run (ISO).
        - ``n_audits`` / ``n_samples``: totals.
        - ``daily``: per-day buckets for dashboards.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with get_db_session() as session:
        rows = session.execute(
            select(IntegrityAudit)
            .where(IntegrityAudit.audited_at >= cutoff)
            .order_by(desc(IntegrityAudit.audited_at))
        ).scalars().all()

        n_audits = len(rows)
        n_samples = sum(r.sample_size for r in rows)
        n_contradicted = sum(r.n_contradicted for r in rows)
        n_supported = sum(r.n_supported for r in rows)
        n_ambiguous = sum(r.n_ambiguous for r in rows)
        error_rate = (n_contradicted / n_samples) if n_samples else 0.0
        last_audit_at = rows[0].audited_at.isoformat() if rows else None

        # Per-day buckets (YYYY-MM-DD in UTC)
        daily: dict[str, dict] = {}
        for r in rows:
            k = r.audited_at.astimezone(timezone.utc).date().isoformat()
            bucket = daily.setdefault(k, {"sampled": 0, "contradicted": 0,
                                          "supported": 0, "ambiguous": 0})
            bucket["sampled"] += r.sample_size
            bucket["contradicted"] += r.n_contradicted
            bucket["supported"] += r.n_supported
            bucket["ambiguous"] += r.n_ambiguous

        # Count flagged and rejected ingestions in the same window for context
        flagged_stmt = (
            select(func.count())
            .select_from(IngestedEntity)
            .where(
                and_(
                    IngestedEntity.created_at >= cutoff,
                    IngestedEntity.status == "flagged",
                )
            )
        )
        flagged = session.execute(flagged_stmt).scalar() or 0
        return {
            "data": {
                "window_days": days,
                "corpus_error_rate": round(error_rate, 4),
                "integrity_score": round(1 - error_rate, 4),
                "n_audits": n_audits,
                "n_samples": n_samples,
                "n_supported": n_supported,
                "n_ambiguous": n_ambiguous,
                "n_contradicted": n_contradicted,
                "last_audit_at": last_audit_at,
                "flagged_ingestions_in_window": flagged,
                "daily": [
                    {"date": k, **v} for k, v in sorted(daily.items())
                ],
            }
        }


@router.get("/entity/{entity_id}")
async def integrity_for_entity(entity_id: int):
    """Return the integrity_meta records for every ingestion of this entity."""
    with get_db_session() as session:
        rows = session.execute(
            select(IngestedEntity)
            .where(IngestedEntity.entity_name_normalized.isnot(None))
            # Fetch by entity id — ingestions are linked via cultural match
            # done in normalizer. For now we allow lookup by raw ext id.
            .where(IngestedEntity.id == entity_id)
        ).scalars().all()
        if not rows:
            raise HTTPException(status_code=404, detail="no ingestions")
        return {"data": [
            {
                "ingestion_id": r.id,
                "entity_name": r.entity_name_raw,
                "source_id": r.source_id,
                "model": r.llm_model_used,
                "prompt_version": r.llm_prompt_version,
                "integrity_meta": r.integrity_meta,
                "status": r.status,
            }
            for r in rows
        ]}


@router.get("/recent_audits")
async def recent_audits(limit: int = Query(10, ge=1, le=100)):
    with get_db_session() as session:
        rows = session.execute(
            select(IntegrityAudit)
            .order_by(desc(IntegrityAudit.audited_at))
            .limit(limit)
        ).scalars().all()
        return {"data": [
            {
                "id": r.id,
                "audited_at": r.audited_at.isoformat(),
                "sample_size": r.sample_size,
                "n_supported": r.n_supported,
                "n_ambiguous": r.n_ambiguous,
                "n_contradicted": r.n_contradicted,
                "error_rate": float(r.n_contradicted) / r.sample_size if r.sample_size else 0.0,
                "oracle_model": r.oracle_model,
            }
            for r in rows
        ]}
