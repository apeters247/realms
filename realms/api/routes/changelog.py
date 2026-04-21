"""Stream R — weekly changelog feed.

Groups new entities / sources / relationships / integrity-audit rows by
ISO week. Powers both the /changelog page in the UI and the /changelog.rss
subscribable feed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response
from sqlalchemy import and_, func, select

from realms.models import Entity, EntityRelationship, IngestionSource, IntegrityAudit
from realms.utils.database import get_db_session

router = APIRouter()


def _iso_week(dt: datetime) -> str:
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _week_bounds(week_key: str) -> tuple[datetime, datetime]:
    year, w = week_key.split("-W")
    monday = datetime.fromisocalendar(int(year), int(w), 1).replace(tzinfo=timezone.utc)
    return monday, monday + timedelta(days=7)


def _build_changelog(weeks: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(weeks=weeks)
    out: dict[str, dict] = {}

    with get_db_session() as session:
        # New entities
        for e in session.execute(
            select(Entity).where(Entity.created_at >= cutoff).order_by(Entity.created_at.desc())
        ).scalars():
            k = _iso_week(e.created_at)
            bucket = out.setdefault(k, {
                "week": k, "entities": [], "sources": [], "relationships": 0,
                "integrity_audits": [],
            })
            if len(bucket["entities"]) < 40:
                bucket["entities"].append({"id": e.id, "name": e.name})
            bucket["entity_count"] = bucket.get("entity_count", 0) + 1

        # New sources (completed)
        for s in session.execute(
            select(IngestionSource)
            .where(and_(
                IngestionSource.processed_at.isnot(None),
                IngestionSource.processed_at >= cutoff,
                IngestionSource.ingestion_status == "completed",
            ))
            .order_by(IngestionSource.processed_at.desc())
        ).scalars():
            k = _iso_week(s.processed_at)
            bucket = out.setdefault(k, {
                "week": k, "entities": [], "sources": [], "relationships": 0,
                "integrity_audits": [],
            })
            if len(bucket["sources"]) < 20:
                bucket["sources"].append({
                    "id": s.id, "name": s.source_name, "type": s.source_type,
                })
            bucket["source_count"] = bucket.get("source_count", 0) + 1

        # Relationship counts
        rel_counts = session.execute(
            select(
                func.date_trunc("week", EntityRelationship.created_at).label("wk"),
                func.count(EntityRelationship.id),
            )
            .where(EntityRelationship.created_at >= cutoff)
            .group_by("wk")
        ).all()
        for wk_dt, count in rel_counts:
            if not wk_dt:
                continue
            k = _iso_week(wk_dt.replace(tzinfo=timezone.utc) if wk_dt.tzinfo is None else wk_dt)
            bucket = out.setdefault(k, {
                "week": k, "entities": [], "sources": [], "relationships": 0,
                "integrity_audits": [],
            })
            bucket["relationships"] = count

        # Integrity audits
        for a in session.execute(
            select(IntegrityAudit)
            .where(IntegrityAudit.audited_at >= cutoff)
            .order_by(IntegrityAudit.audited_at.desc())
        ).scalars():
            k = _iso_week(a.audited_at)
            bucket = out.setdefault(k, {
                "week": k, "entities": [], "sources": [], "relationships": 0,
                "integrity_audits": [],
            })
            bucket["integrity_audits"].append({
                "id": a.id,
                "sample_size": a.sample_size,
                "error_rate": (a.n_contradicted / a.sample_size) if a.sample_size else 0.0,
                "oracle_model": a.oracle_model,
            })

    weeks_sorted = sorted(out.values(), key=lambda b: b["week"], reverse=True)
    return weeks_sorted


@router.get("/")
async def changelog(weeks: int = Query(12, ge=1, le=52)):
    return {"data": _build_changelog(weeks)}


@router.get(".rss", include_in_schema=False)
async def changelog_rss(request: Request):
    site_host = request.headers.get("x-forwarded-host") or request.url.netloc
    site_proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    origin = f"{site_proto}://{site_host}"
    entries = _build_changelog(weeks=12)

    def _xml_escape(s: str) -> str:
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    items_xml = []
    for wk in entries:
        monday, _ = _week_bounds(wk["week"])
        title = f"Week {wk['week']}: {wk.get('entity_count', 0)} new entities, {wk.get('source_count', 0)} new sources"
        body_lines = []
        if wk.get("entities"):
            names = ", ".join(e["name"] for e in wk["entities"][:12])
            body_lines.append(f"New entities: {names}")
        if wk.get("sources"):
            names = ", ".join(s["name"] for s in wk["sources"][:8])
            body_lines.append(f"New sources: {names}")
        if wk.get("relationships"):
            body_lines.append(f"New relationships: {wk['relationships']}")
        if wk.get("integrity_audits"):
            avg_er = sum(a["error_rate"] for a in wk["integrity_audits"]) / len(wk["integrity_audits"])
            body_lines.append(f"Integrity audits: {len(wk['integrity_audits'])} (avg error rate {avg_er:.3f})")
        body = " · ".join(body_lines) or "No detail this week."

        items_xml.append(
            f"""<item>
  <title>{_xml_escape(title)}</title>
  <link>{origin}/app/changelog/#{wk['week']}</link>
  <guid isPermaLink="false">realms-changelog-{wk['week']}</guid>
  <pubDate>{monday.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>
  <description>{_xml_escape(body)}</description>
</item>"""
        )

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>REALMS changelog</title>
  <link>{origin}/app/changelog/</link>
  <description>Weekly activity log: new entities, new sources, integrity audits.</description>
  <language>en</language>
  <atom:link href="{origin}/changelog.rss" rel="self" type="application/rss+xml" />
  {chr(10).join(items_xml)}
</channel>
</rss>
"""
    return Response(content=rss, media_type="application/rss+xml")
