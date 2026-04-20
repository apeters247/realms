"""Stream R — public error-reporting endpoint.

Rate-limited, no captcha (IP-hash de-dupes and rate limiter are enough for
the expected low volume). No email is required; if supplied we keep it for
follow-up only, never for marketing.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select

from realms.api.dependencies import require_review_token
from realms.api.rate_limit import limiter
from realms.models import FeedbackReport
from realms.utils.database import get_db_session

router = APIRouter()


ALLOWED_ISSUE_TYPES = {
    "wrong_fact",          # e.g., incorrect alignment or realm
    "missing_source",      # claim lacks citation
    "wrong_relationship",  # a relationship that shouldn't exist
    "missing_relationship",
    "misattribution",      # attributes tradition incorrectly
    "ethics",              # respectful-use concern
    "typo",
    "other",
}


class FeedbackPayload(BaseModel):
    entity_id: Optional[int] = None
    field: Optional[str] = Field(default=None, max_length=100)
    issue_type: str = Field(..., max_length=40)
    message: str = Field(..., min_length=10, max_length=4000)
    reporter_email: Optional[str] = Field(default=None, max_length=200)


def _hash_ip(ip: str) -> str:
    return hashlib.sha256(f"realms:{ip}".encode("utf-8")).hexdigest()[:32]


@router.post("")
@limiter.limit("10/hour")
async def submit_feedback(payload: FeedbackPayload, request: Request):
    issue = payload.issue_type.lower().strip()
    if issue not in ALLOWED_ISSUE_TYPES:
        raise HTTPException(status_code=400, detail=f"issue_type must be one of {sorted(ALLOWED_ISSUE_TYPES)}")

    client_ip = request.client.host if request.client else "unknown"
    ip_hash = _hash_ip(client_ip)

    # De-dupe: reject if same IP submitted identical message in last 24h.
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    with get_db_session() as session:
        existing = session.execute(
            select(FeedbackReport)
            .where(FeedbackReport.reporter_ip_hash == ip_hash)
            .where(FeedbackReport.created_at >= cutoff)
            .where(FeedbackReport.message == payload.message)
        ).scalars().first()
        if existing:
            return {"data": {"id": existing.id, "status": "duplicate", "message": "already received"}}

        row = FeedbackReport(
            entity_id=payload.entity_id,
            field=payload.field,
            issue_type=issue,
            message=payload.message,
            reporter_email=payload.reporter_email,
            reporter_ip_hash=ip_hash,
            status="open",
        )
        session.add(row)
        session.commit()
        return {"data": {"id": row.id, "status": "received"}}


@router.get("/stats")
async def feedback_stats():
    """Public aggregate stats — no message contents exposed here."""
    with get_db_session() as session:
        by_type = session.execute(
            select(FeedbackReport.issue_type, func.count())
            .group_by(FeedbackReport.issue_type)
        ).all()
        by_status = session.execute(
            select(FeedbackReport.status, func.count())
            .group_by(FeedbackReport.status)
        ).all()
        return {"data": {
            "by_issue_type": {k: v for k, v in by_type},
            "by_status": {k: v for k, v in by_status},
        }}


@router.get("")
async def list_feedback(
    status: Optional[str] = Query(None),
    issue_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    reviewer: str = Depends(require_review_token),
):
    """Researcher-only: inspect feedback queue. Returns message contents."""
    with get_db_session() as session:
        stmt = select(FeedbackReport).order_by(desc(FeedbackReport.created_at)).limit(limit)
        if status:
            stmt = stmt.where(FeedbackReport.status == status.strip())
        if issue_type:
            stmt = stmt.where(FeedbackReport.issue_type == issue_type.strip())
        rows = session.execute(stmt).scalars().all()
        return {"data": [
            {
                "id": r.id, "entity_id": r.entity_id, "field": r.field,
                "issue_type": r.issue_type, "message": r.message,
                "reporter_email": r.reporter_email, "status": r.status,
                "resolution": r.resolution,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]}
