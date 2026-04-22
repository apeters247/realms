"""Cluster the tail of rare tradition tags into their canonical parents.

After the first canonicalize_traditions.py pass, 58% of traditions remain
singletons — LLM-coined variants like "Aboriginal Australian mythology",
"Akkadian mythology", "Ancient Mesopotamian religion". Most of these
simply wrap a real canonical tag in a suffix ("mythology", "religion",
"folklore", "tradition", "beliefs").

This script:

  1. Reads the current popular-tag set (entity_count ≥ MIN_POPULAR_CT).
     These are the **canonical** pool.
  2. For every rare tag (entity_count < MIN_POPULAR_CT), tries to map it
     to a canonical tag via:
       a. Suffix-strip rules ("X mythology" → "X" when "X" is popular)
       b. Prefix-strip rules ("Ancient X" → "X" when "X" is popular)
       c. Exact substring containment ("Slavic mythology" contains "Slavic")
       d. Fuzzy match (diacritic-strip + lowercase)
  3. Rewrites every entity's cultural_associations to use canonical tags
     where possible; tags that can't be mapped are left as-is (but the
     review queue can surface them).

Dry-run by default. Writes audit JSONL.

Usage:
    docker exec realms-api python -m scripts.cluster_traditions
    docker exec realms-api python -m scripts.cluster_traditions --apply
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from realms.models import Entity
from realms.utils.database import get_db_session

log = logging.getLogger("realms.cluster_traditions")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


MIN_POPULAR_COUNT = 10  # a tag with ≥10 entities is treated as canonical


# Suffixes that a rare tag might wrap around a popular one.
STRIPPABLE_SUFFIXES = [
    r"\bmythology\b",
    r"\breligion\b",
    r"\bfolklore\b",
    r"\btradition\b",
    r"\btraditions\b",
    r"\bbelief(s)?\b",
    r"\bculture\b",
    r"\bpeople(s)?\b",
    r"\bpantheon\b",
    r"\bfaith\b",
    r"\bcosmology\b",
    r"\bspirituality\b",
    r"\bpaganism\b",
    r"\btribal religion\b",
    r"\blegend(s)?\b",
    r"\btale(s)?\b",
    r"\btheology\b",
]

STRIPPABLE_PREFIXES = [
    r"\bancient\b",
    r"\bclassical\b",
    r"\bmedieval\b",
    r"\bearly\b",
    r"\bmodern\b",
    r"\bcontemporary\b",
    r"\btraditional\b",
]


def _normalise(s: str) -> str:
    nfd = unicodedata.normalize("NFD", s or "")
    no_dia = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", no_dia.lower().strip())


def _strip_wrapping(tag: str) -> str:
    """Try stripping each suffix / prefix; return the inner term."""
    t = tag
    # Strip trailing suffix tokens repeatedly.
    for _ in range(3):
        changed = False
        for pat in STRIPPABLE_SUFFIXES:
            new = re.sub(r"(?i)(.*)\s+" + pat + r"\s*$", r"\1", t).strip()
            if new and new != t:
                t = new
                changed = True
        if not changed:
            break
    # Strip leading prefix tokens repeatedly.
    for _ in range(3):
        changed = False
        for pat in STRIPPABLE_PREFIXES:
            new = re.sub(r"(?i)^\s*" + pat + r"\s+(.*)", r"\1", t).strip()
            if new and new != t:
                t = new
                changed = True
        if not changed:
            break
    return t.strip()


def build_canonical_pool(entities) -> dict[str, str]:
    """Return a map of normalised_tag → original_canonical_form."""
    counts: Counter = Counter()
    forms: dict[str, str] = {}
    for e in entities:
        cs = e.cultural_associations if isinstance(e.cultural_associations, list) else []
        for t in cs:
            if not t:
                continue
            n = _normalise(t)
            counts[n] += 1
            # Keep the first encountered original form as the canonical display form.
            forms.setdefault(n, t)
    # Include any tag whose count is high enough.
    return {n: forms[n] for n, c in counts.items() if c >= MIN_POPULAR_COUNT}


def map_tag(tag: str, canonical: dict[str, str]) -> tuple[str, str | None]:
    """Return (display_form, reason) for where this tag should map.
    If no mapping is found, returns the original tag unchanged + None."""
    if not tag:
        return tag, None
    n = _normalise(tag)
    # Already canonical.
    if n in canonical:
        return canonical[n], None
    # Strip wrapping words and see if the inner term is canonical.
    stripped = _strip_wrapping(tag)
    sn = _normalise(stripped)
    if sn != n and sn in canonical:
        return canonical[sn], f"strip-wrapping→{stripped}"
    # Substring containment: find a canonical tag that is wholly contained.
    words = sn.split()
    if len(words) >= 2:
        # Try progressively smaller n-grams of this tag.
        for k in range(len(words), 0, -1):
            for i in range(len(words) - k + 1):
                candidate = " ".join(words[i:i + k])
                if candidate in canonical and len(candidate) >= 4:
                    return canonical[candidate], f"containment→{candidate}"
    return tag, None


def run(apply: bool) -> dict:
    with get_db_session() as session:
        entities = session.execute(select(Entity)).scalars().all()

        canonical = build_canonical_pool(entities)
        log.info("canonical pool: %d tags (≥%d entities each)",
                 len(canonical), MIN_POPULAR_COUNT)

        renames: Counter = Counter()
        per_entity_changes = 0

        for e in entities:
            cs = e.cultural_associations if isinstance(e.cultural_associations, list) else []
            if not cs:
                continue
            new_tags: list[str] = []
            seen_norm: set[str] = set()
            changed = False
            for t in cs:
                mapped, reason = map_tag(t, canonical)
                if mapped != t and reason:
                    renames[(t, mapped, reason)] += 1
                    changed = True
                nn = _normalise(mapped)
                if nn in seen_norm:
                    continue
                seen_norm.add(nn)
                new_tags.append(mapped)
            if changed or len(new_tags) != len(cs):
                per_entity_changes += 1
                if apply:
                    e.cultural_associations = new_tags
        if apply:
            session.commit()

    # Audit.
    audit_dir = Path("data")
    audit_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    audit = audit_dir / f"cluster_traditions_{stamp}.jsonl"
    with audit.open("w", encoding="utf-8") as fh:
        for (orig, new, reason), n in renames.most_common():
            fh.write(json.dumps({
                "type": "rename", "from": orig, "to": new, "reason": reason, "count": n,
            }, ensure_ascii=False) + "\n")

    summary = {
        "canonical_pool_size": len(canonical),
        "distinct_renames": len(renames),
        "total_rename_applications": sum(renames.values()),
        "entities_changed": per_entity_changes,
        "dry_run": not apply,
        "audit_file": str(audit),
    }
    log.info("%s", summary)
    print(json.dumps(summary, indent=2))
    # Show the top renames.
    print("\nTop 30 renames:")
    for (orig, new, reason), n in renames.most_common(30):
        print(f"  {n:4d} × {orig!r:45s} → {new!r}  [{reason}]")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    run(apply=args.apply)


if __name__ == "__main__":
    main()
