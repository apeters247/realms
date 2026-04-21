"""Stream D — remove Tier 3/4 entities that slipped into the DB.

Scans every Entity and flags those that:
  1. Have any cultural_associations matching a blocked tag
     (dmt-experiences, ayahuasca-ceremonies, psychonautic-culture, etc.)
  2. Are only linked to blocked IngestionSources
  3. Match a blocked name substring (machine elves, tulpa, contactee, …)

Default mode is dry-run. Use ``--apply`` to actually delete.

Writes an audit file to ``data/purge_audit_<timestamp>.jsonl`` listing every
entity it touched, with the reason. Commit that alongside the deletion so
there's a forensic trail.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select

from realms.models import Entity, IngestedEntity, IngestionSource
from realms.utils.database import get_db_session

log = logging.getLogger("realms.purge")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


BLOCKED_CULTURE_TOKENS = {
    # Tier 3
    "dmt experiences", "dmt-experiences",
    "ayahuasca ceremonies", "ayahuasca-ceremonies",
    "psychonautic culture", "psychonautic-culture",
    "psychedelic",
    "entheogenic hyperspace",
    # Tier 4
    "chaos magic",
    "thelema",
    "ceremonial magic",
    "new age",
    "ufo religion",
    "contactee",
    "tulpamancy",
    "slenderman",
    "creepypasta",
}

BLOCKED_NAME_SUBSTR = {
    "machine elf", "machine elves",
    "tulpa",
    "contactee",
    "extraterrestrial",
    "chaos sigil",
    "slenderman",
}


def _matches_any(haystack: str, needles: set[str]) -> bool:
    if not haystack:
        return False
    h = haystack.lower()
    return any(n in h for n in needles)


def _is_blocked_entity(e: Entity) -> tuple[bool, str]:
    if _matches_any(e.name or "", BLOCKED_NAME_SUBSTR):
        return True, f"blocked_name_substr:{e.name}"
    cultures = [str(c).lower() for c in (e.cultural_associations or [])]
    if not cultures:
        return False, ""
    # Only purge when *all* cultural_associations are blocked. If a single
    # legitimate tradition (Yoruba, Cherokee, …) is also cited, we keep the
    # entity and flag the problematic tag for review via the existing
    # review queue, not via deletion.
    blocked_cultures = [c for c in cultures if _matches_any(c, BLOCKED_CULTURE_TOKENS)]
    if blocked_cultures and len(blocked_cultures) == len(cultures):
        return True, f"all_cultures_blocked:{blocked_cultures[0]}"
    return False, ""


def _is_blocked_source(src: IngestionSource) -> bool:
    tokens = {
        "dmt experiences", "ayahuasca ceremonies", "psychonautic",
        "chaos magic", "thelema", "contactee", "tulpamancy",
    }
    return _matches_any(src.source_name or "", tokens) or _matches_any(src.url or "", tokens)


def purge(apply: bool) -> dict:
    deleted: list[dict] = []
    kept_count = 0

    with get_db_session() as session:
        # Pass 1 — entities with blocked cultures or names
        for e in session.execute(select(Entity)).scalars():
            blocked, reason = _is_blocked_entity(e)
            if blocked:
                deleted.append({
                    "id": e.id,
                    "name": e.name,
                    "reason": reason,
                    "cultural_associations": e.cultural_associations or [],
                })
            else:
                kept_count += 1

        # Pass 2 — entities whose only IngestedEntity rows come from blocked sources
        ext_rows = session.execute(
            select(IngestedEntity.entity_name_normalized, IngestionSource)
            .join(IngestionSource, IngestedEntity.source_id == IngestionSource.id)
        ).all()
        by_name: dict[str, list[IngestionSource]] = {}
        for name, src in ext_rows:
            if not name:
                continue
            by_name.setdefault(name, []).append(src)
        for norm, srcs in by_name.items():
            if all(_is_blocked_source(s) for s in srcs):
                # look up the matching entity
                ent = session.execute(
                    select(Entity).where(Entity.name.ilike(norm))
                ).scalars().first()
                if ent and not any(d["id"] == ent.id for d in deleted):
                    deleted.append({
                        "id": ent.id,
                        "name": ent.name,
                        "reason": "all_sources_blocked",
                        "source_names": [s.source_name for s in srcs],
                    })

        log.info("purge candidates: %d; keep: %d", len(deleted), kept_count)

        if apply:
            ids = [d["id"] for d in deleted]
            session.execute(delete(Entity).where(Entity.id.in_(ids)))
            session.commit()
            log.info("deleted %d entities", len(ids))

    # audit file
    audit_dir = Path("data")
    audit_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    audit_path = audit_dir / f"purge_audit_{stamp}.jsonl"
    with audit_path.open("w", encoding="utf-8") as fh:
        for row in deleted:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    log.info("audit → %s", audit_path)

    return {
        "purged": len(deleted) if apply else 0,
        "candidates": len(deleted),
        "kept": kept_count,
        "dry_run": not apply,
        "audit_file": str(audit_path),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true",
                   help="actually delete (default is dry-run)")
    args = p.parse_args()
    summary = purge(apply=args.apply)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
