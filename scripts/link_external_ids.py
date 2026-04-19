"""Link REALMS entities to external authorities (Wikidata, VIAF).

For each entity missing a given external_ids key, run the matcher and either
auto-accept (confidence >= threshold + 2x gap over runner-up) or write a
review_actions row with action='external_link_suggest' so a human can pick.

Usage (inside container):
    docker exec realms-api python -m scripts.link_external_ids --system wikidata
    docker exec realms-api python -m scripts.link_external_ids --system viaf --limit 10
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import asdict

from sqlalchemy import select

from realms.models import Entity, ReviewAction
from realms.services.external_linker import (
    VIAFMatcher,
    WikidataMatcher,
    auto_accept_decision,
)
from realms.utils.database import get_db_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("realms.link_external")


REVIEWER = os.getenv("REALMS_REVIEW_REVIEWER", "link-bot")


def _run_system(system: str, *, limit: int | None, min_confidence: float, dry_run: bool) -> int:
    if system == "wikidata":
        matcher = WikidataMatcher()
    elif system == "viaf":
        matcher = VIAFMatcher()
    else:
        raise SystemExit(f"unknown system: {system}")

    accepted = 0
    queued = 0
    scanned = 0
    with get_db_session() as session:
        stmt = select(Entity).order_by(Entity.consensus_confidence.desc().nullslast(), Entity.id.asc())
        entities = list(session.execute(stmt).scalars().all())
        if limit:
            entities = entities[:limit]

        for entity in entities:
            scanned += 1
            ext_map = dict(entity.external_ids or {})
            if system in ext_map:
                continue
            try:
                candidates = matcher.match(entity.name, description=entity.description)
            except Exception as exc:  # noqa: BLE001
                log.warning("matcher failed for %r: %s", entity.name, exc)
                continue

            if not candidates:
                continue

            chosen = auto_accept_decision(candidates, min_confidence=min_confidence)
            if chosen is not None:
                accepted += 1
                if dry_run:
                    log.info("[DRY] %s=%s for %r (conf=%.2f)",
                             system, chosen.external_id, entity.name, chosen.confidence)
                    continue
                ext_map[system] = chosen.external_id
                entity.external_ids = ext_map
                session.add(ReviewAction(
                    entity_id=entity.id,
                    reviewer=REVIEWER,
                    action="external_link_auto",
                    field=system,
                    old_value=None,
                    new_value={"external_ids": ext_map, "label": chosen.label,
                               "confidence": chosen.confidence},
                ))
            else:
                queued += 1
                if dry_run:
                    log.info("[DRY] queue for review: %r → %d candidates",
                             entity.name, len(candidates))
                    continue
                session.add(ReviewAction(
                    entity_id=entity.id,
                    reviewer=REVIEWER,
                    action="external_link_suggest",
                    field=system,
                    new_value={"candidates": [asdict(c) for c in candidates[:5]]},
                ))

            if not dry_run and (accepted + queued) % 25 == 0:
                session.commit()

        if not dry_run:
            session.commit()

    log.info("system=%s scanned=%d accepted=%d queued=%d",
             system, scanned, accepted, queued)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", choices=("wikidata", "viaf"), required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--min-confidence", type=float, default=0.85)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return _run_system(
        args.system,
        limit=args.limit,
        min_confidence=args.min_confidence,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())
