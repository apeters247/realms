"""Purge obvious hallucinations / Tier-3/4 slippage from the corpus.

Complements ``purge_out_of_scope.py`` which only checked the blocklist at
seed time. This one scans the *live* entity table and targets:

  1. Fictional / modern / pop-culture cultural_associations
     (DC Comics, Disney, Marvel Comics, video game, anime, candy, …)
  2. Literal null / undefined / unknown entity_type values
  3. Entities whose every cultural_association is on the blocklist
     (if at least one legit tradition is present the entity survives and
     only the bad tag is stripped)

Writes audit JSONL. Safe to re-run; dry-run by default.

Usage:
    docker exec realms-api python -m scripts.purge_hallucinations
    docker exec realms-api python -m scripts.purge_hallucinations --apply
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text, update

from realms.models import Entity, ReviewAction
from realms.utils.database import get_db_session

log = logging.getLogger("realms.purge_halluc")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# Fictional / modern / pop-culture tradition tags.
# Word-boundary-anchored patterns so we don't match legitimate traditions
# (e.g., "manga" must not match "Mangaia", "Mangareva"; "dmt " must not
# match "admitance"; etc.)
FICTION_PATTERNS: list[re.Pattern[str]] = [re.compile(p, re.IGNORECASE) for p in [
    r"\bdc comics\b",
    r"\bmarvel comics\b",
    r"\bharvey comics\b",
    r"\bamerican comics\b",
    r"^comics$",
    r"\bmarvel cinematic\b",
    r"\bdisney\b",
    r"\bfantasia\b",
    r"\bamerican horror story\b",
    r"\banime\b",
    r"\bmanga\b(?! ia| areva| arev| alam)",   # real "manga" but not Mangaia, Mangareva etc.
    r"\bjapanese manga\b",
    r"\bvideo game(s)?\b",
    r"\bvideo game mythology\b",
    r"\bfandom\b",
    r"\bcreepypasta\b",
    r"\bcandy\b",
    r"\bcandy people\b",
    r"\btolkien\b",
    r"\bharry potter\b",
    r"\browling\b",
    r"^potter$",
    r"\bpotter['']s wheel\b",
    r"\bfan ?fiction\b",
    r"\bworld of warcraft\b",
    r"\bdungeons and dragons\b",
    r"\bdungeons & dragons\b",
    r"\bd&d\b", r"\bdnd\b",
    r"\btwilight zone\b",
    r"\bstar wars\b",
    r"\bstar trek\b",
    r"\bthe matrix\b",
    r"\bslenderman\b",
    r"\btulpa(mancy)?\b",
    r"\bchaos magi(c|ck)\b",
    r"\bthelema\b",
    r"\baleister crowley\b",
    r"\bcontactee\b",
    r"\bufo religion\b",
    r"\bdmt experience(s)?\b",
    r"\bdmt research\b",
    r"\bpsychedelic culture\b",
    r"\bpsychonautic\b",
    r"\bwalt disney\b",
]]

# Non-tradition category tags — these describe a *period* or *genre* of
# source material, not a religion/folklore tradition. We keep the entity
# but strip the tag when a real tradition is also present; when the tag
# is the only culture, we clear the field rather than delete the entity
# (it may still be a real entity deserving review).
NON_TRADITION_PATTERNS: list[re.Pattern[str]] = [re.compile(p, re.IGNORECASE) for p in [
    r"\bliterature\b",
    r"\btragedy\b",
    r"\bphilosophy\b",
    r"\bcinema\b",
    r"\bfilm\b",
    r"\bpottery\b",
    r"\bceramic(s)?\b",
    r"\bperiod\b",
    r"\bera\b",
]]


def _matches_any(tag: str, patterns: list[re.Pattern[str]]) -> bool:
    if not tag:
        return False
    return any(p.search(tag) for p in patterns)


def _hits(tags: list[str], patterns: list[re.Pattern[str]]) -> list[str]:
    return [t for t in (tags or []) if _matches_any(t, patterns)]


def purge(apply: bool) -> dict:
    deleted_ids: list[dict] = []
    stripped: list[dict] = []
    null_typed: list[int] = []

    with get_db_session() as session:
        rows = session.execute(select(Entity)).scalars().all()

        for e in rows:
            cultures = e.cultural_associations if isinstance(e.cultural_associations, list) else []
            if not cultures:
                continue

            bad_fiction = _hits(cultures, FICTION_PATTERNS)
            bad_non_trad = _hits(cultures, NON_TRADITION_PATTERNS)

            # Case 1: every tag is a fiction marker → purge entirely.
            # Fiction tags are strong enough signal that we delete the entity.
            if bad_fiction and len(bad_fiction) == len(cultures):
                deleted_ids.append({
                    "id": e.id, "name": e.name, "reason": "all-fiction cultures",
                    "cultures": cultures,
                })
                if apply:
                    e.review_status = "out_of_scope"
                continue

            # Case 2: at least one legit tag plus some fiction/non-trad tags
            # → strip the bad ones, keep the entity. When stripping would
            # leave zero cultures, we STILL keep the entity (only clearing
            # the culture list) because non-tradition tags (like "Ancient
            # Greek philosophy") often indicate a real entity whose tag
            # was just wrong — deleting would lose data.
            strip_set = set(bad_fiction) | set(bad_non_trad)
            if strip_set:
                new_cultures = [c for c in cultures if c not in strip_set]
                if not new_cultures and bad_fiction:
                    deleted_ids.append({
                        "id": e.id, "name": e.name,
                        "reason": "only fiction tags after strip",
                        "cultures": cultures,
                    })
                    if apply:
                        e.review_status = "out_of_scope"
                    continue
                # Keep entity; clear or shrink cultural_associations.
                stripped.append({
                    "id": e.id, "name": e.name,
                    "before": cultures, "after": new_cultures,
                    "dropped": list(strip_set),
                })
                if apply:
                    e.cultural_associations = new_cultures

        # Case 3: fix literal 'null'/'undefined'/'unknown' entity_type.
        bad_types = session.execute(
            select(Entity).where(Entity.entity_type.in_(
                ["null", "None", "undefined", "unknown", "Null", "UNKNOWN"]
            ))
        ).scalars().all()
        for e in bad_types:
            null_typed.append(e.id)
            if apply:
                e.entity_type = None

        if apply:
            # Log review_actions for deletions.
            for d in deleted_ids:
                session.add(ReviewAction(
                    entity_id=d["id"],
                    reviewer="purge_hallucinations",
                    action="mark_out_of_scope",
                    field=None,
                    old_value={"cultures": d["cultures"]},
                    new_value={"reason": d["reason"]},
                    note=f"Auto-purge: {d['reason']}",
                ))
            session.commit()

    audit_dir = Path("data")
    audit_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    audit = audit_dir / f"purge_halluc_audit_{stamp}.jsonl"
    with audit.open("w", encoding="utf-8") as fh:
        for d in deleted_ids:
            fh.write(json.dumps({"type": "delete", **d}, ensure_ascii=False) + "\n")
        for d in stripped:
            fh.write(json.dumps({"type": "strip", **d}, ensure_ascii=False) + "\n")
        for eid in null_typed:
            fh.write(json.dumps({"type": "null_type", "id": eid}) + "\n")

    summary = {
        "entities_marked_out_of_scope": len(deleted_ids),
        "entities_with_tags_stripped": len(stripped),
        "entities_with_null_type_fixed": len(null_typed),
        "dry_run": not apply,
        "audit_file": str(audit),
    }
    log.info("%s", summary)
    print(json.dumps(summary, indent=2))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    purge(apply=args.apply)


if __name__ == "__main__":
    main()
