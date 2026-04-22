"""Merge transliteration / diacritic / phonetic variants of the same entity.

Catches cases the name-stem dedup misses — e.g.:

    "Oshun"   (67)   culture=Yoruba
    "Ọ̀ṣun"    (1957) culture=Yoruba
    "Oxum"    (183)  culture=Candomblé   ← leave alone (different tradition)

Strategy: normalise by
    1. NFD + strip combining marks
    2. Lowercase
    3. Replace any "sh", "x", "ch" with a single stem token (sibilant unification)
    4. Collapse whitespace

Entities whose normalised form matches AND whose cultural_associations
overlap on at least one canonical tag get merged. Uses the same audit-
safe merge_pair from the existing dedupe_entities script.

Usage:
    docker exec realms-api python -m scripts.dedupe_transliteration --dry-run
    docker exec realms-api python -m scripts.dedupe_transliteration --apply
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from realms.models import Entity
from realms.utils.database import get_db_session

# Re-use the existing merge machinery.
from scripts.dedupe_entities import merge_pair, _cultures_overlap, _pick_survivor

log = logging.getLogger("realms.dedupe_translit")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# Sibilant / phonetic unifications that collapse common transliteration
# choices for the same underlying name.
_SIBILANT_RE = re.compile(r"sh|ś|ş|ṣ|š|sz|ç|ch|ks|x", re.IGNORECASE)


def _translit_key(name: str) -> str:
    if not name:
        return ""
    # Remove parenthetical disambiguators.
    n = re.sub(r"\s*\([^)]*\)\s*", " ", name).strip()
    # NFD + strip combining marks.
    nfd = unicodedata.normalize("NFD", n)
    no_dia = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    low = no_dia.lower()
    # Unify common sibilant transliterations → "s".
    unified = _SIBILANT_RE.sub("s", low)
    # Drop non-alphanumeric, collapse whitespace.
    cleaned = re.sub(r"[^a-z0-9]+", "", unified)
    return cleaned


def find_groups() -> dict[str, list[Entity]]:
    with get_db_session() as session:
        rows = session.execute(
            select(Entity).where(Entity.review_status != "merged")
        ).scalars().all()
    groups: dict[str, list[Entity]] = defaultdict(list)
    for e in rows:
        k = _translit_key(e.name or "")
        if len(k) < 3:  # too short → risk of over-merging
            continue
        groups[k].append(e)
    return {k: v for k, v in groups.items() if len(v) >= 2}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()

    groups = find_groups()
    log.info("candidate transliteration groups: %d", len(groups))

    merges: list[dict] = []
    skipped: list[dict] = []

    with get_db_session() as session:
        for key, group in groups.items():
            # Sort by consensus confidence desc (best becomes survivor).
            group = sorted(group, key=lambda x: -(x.consensus_confidence or 0))
            survivor = session.merge(group[0])

            for candidate in group[1:]:
                candidate = session.merge(candidate)
                # Only merge when cultures overlap. Different cultures
                # means different tradition — the Oxum/Oshun/Ọ̀ṣun
                # distinction between Candomblé and Yoruba should stay
                # as semantic link (syncretized_with), not a merge.
                if not _cultures_overlap(
                    survivor.cultural_associations, candidate.cultural_associations
                ):
                    skipped.append({
                        "survivor": survivor.name, "candidate": candidate.name,
                        "reason": "culture mismatch",
                        "a_culture": survivor.cultural_associations,
                        "b_culture": candidate.cultural_associations,
                    })
                    continue

                new_survivor, loser = _pick_survivor(survivor, candidate)
                if args.apply:
                    audit = merge_pair(session, new_survivor, loser)
                    audit["reason"] = "transliteration variant"
                    audit["translit_key"] = key
                    merges.append(audit)
                    survivor = new_survivor
                else:
                    merges.append({
                        "survivor_id": new_survivor.id,
                        "survivor_name": new_survivor.name,
                        "loser_id": loser.id,
                        "loser_name": loser.name,
                        "translit_key": key,
                    })

            if args.apply:
                session.commit()

    log.info("%d merges, %d skipped (culture mismatch)", len(merges), len(skipped))

    # Audit log
    audit_dir = Path("data")
    audit_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    audit_path = audit_dir / f"dedupe_translit_audit_{stamp}.jsonl"
    with audit_path.open("w", encoding="utf-8") as fh:
        for m in merges:
            fh.write(json.dumps({"type": "merge", **m}, ensure_ascii=False, default=str) + "\n")
        for s in skipped:
            fh.write(json.dumps({"type": "skip", **s}, ensure_ascii=False, default=str) + "\n")

    print(json.dumps({
        "candidate_groups": len(groups),
        "merges": len(merges),
        "skipped_culture_mismatch": len(skipped),
        "dry_run": not args.apply,
        "audit_file": str(audit_path),
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
