"""Entity-level deduplication with audit trail.

The tradition-canonicalizer handles tag dedup (Christian / Christianity /
Catholic). This script tackles the remaining problem — entity rows that
should be one row but aren't:

  - ``Encantado`` (id 276) + ``Encantado (mythology)`` (id 3)
  - ``Judas Iscariot`` (id 594, culture=Christian) + ``Judas Iscariot`` (id 598)
  - ``Gbădu`` (id 19) + ``Gbǎdù`` (id 31)   (diacritic variants)

Merge rule: within each normalised-name group, two rows merge iff:
  - Both have at least one cultural_association in common, OR
  - Both have zero cultural_associations, OR
  - They share any external_id

We intentionally DO NOT merge:
  - Rows whose names differ by a parenthetical disambiguator
    (e.g., ``Bhagavati (Pernem)`` stays separate from ``Bhagavati``)
  - Rows whose cultures are fully disjoint
    (``Eurynome`` Greek + ``Eurynome (Queen of the Titans)`` Greek — those
     match on culture, so they WOULD merge)

Merge action:
  - Pick the survivor as the row with higher consensus_confidence
    (tiebreak: lower id)
  - Union: alternate_names, powers, domains, cultural_associations,
    geographical_associations, external_ids, provenance_sources,
    extraction_instances
  - Re-point IngestedEntity.entity_name_normalized toward survivor.name
  - Move EntityRelationship rows (source_entity_id / target_entity_id)
    onto the survivor
  - Mark the loser row review_status='merged' and log a ReviewAction row
    with action='dedupe_merge', new_value={'survivor_id': N}
  - Do NOT DELETE the loser; it stays with review_status='merged' as an audit record

Usage:
  docker exec realms-api python -m scripts.dedupe_entities --dry-run
  docker exec realms-api python -m scripts.dedupe_entities --apply
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select, update

from realms.models import Entity, EntityRelationship, IngestedEntity, ReviewAction
from realms.utils.database import get_db_session

log = logging.getLogger("realms.dedupe_entities")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


_WS_RE = re.compile(r"\s+")
_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*")


def _norm_name(s: str | None) -> str:
    if not s:
        return ""
    nfd = unicodedata.normalize("NFD", s)
    no_dia = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return _WS_RE.sub(" ", no_dia.lower().strip())


def _norm_name_stripped(s: str | None) -> str:
    """Normalised name without parenthetical disambiguators."""
    if not s:
        return ""
    stripped = _PAREN_RE.sub(" ", s)
    return _norm_name(stripped)


def _has_paren(s: str | None) -> bool:
    return bool(s and "(" in s and ")" in s)


def _cultures_overlap(a: list | None, b: list | None) -> bool:
    """True if a and b share at least one cultural_association (case-insensitive)."""
    if not a or not b:
        return not a and not b  # both empty is allowed
    na = {_norm_name(x) for x in a if x}
    nb = {_norm_name(x) for x in b if x}
    return bool(na & nb)


def _external_ids_overlap(a: dict | None, b: dict | None) -> bool:
    if not a or not b:
        return False
    for k, v in (a or {}).items():
        if b.get(k) == v and v:
            return True
    return False


def _union_list(a: list | None, b: list | None) -> list:
    seen, out = set(), []
    for x in (a or []) + (b or []):
        if x is None:
            continue
        k = _norm_name(x) if isinstance(x, str) else str(x)
        if k in seen:
            continue
        seen.add(k)
        out.append(x)
    return out


def _union_dict_lists(a: dict | None, b: dict | None) -> dict:
    """For alternate_names-style dict-of-lists."""
    out = dict(a or {})
    for k, vs in (b or {}).items():
        if k not in out:
            out[k] = list(vs or [])
        else:
            out[k] = _union_list(out[k], vs or [])
    return out


def find_dup_groups() -> dict[str, list[Entity]]:
    with get_db_session() as session:
        rows = session.execute(select(Entity)).scalars().all()

    groups: dict[str, list[Entity]] = defaultdict(list)
    for e in rows:
        # Key on stripped+normalised name so "Encantado" matches "Encantado (mythology)".
        # BUT we'll refuse to merge rows whose parenthetical ROLES differ.
        k = _norm_name_stripped(e.name)
        if not k:
            continue
        groups[k].append(e)

    return {k: v for k, v in groups.items() if len(v) >= 2}


def should_merge(a: Entity, b: Entity) -> tuple[bool, str]:
    """Judge whether two same-stem entities should merge."""
    # If one has a paren'd disambiguator and the other doesn't,
    # refuse unless the disambiguator is redundant with the culture.
    if _has_paren(a.name) != _has_paren(b.name):
        # Let through only if cultures overlap AND the paren version's
        # disambiguator doesn't add new semantic info.
        parened = a if _has_paren(a.name) else b
        plain = b if parened is a else a
        paren_text = re.search(r"\(([^)]+)\)", parened.name or "").group(1).lower()
        # If the paren content is just a role hint like "mythology", "goddess",
        # "god", "spirit" — that's redundant, allow merge when cultures align.
        ok_hints = {"mythology", "god", "goddess", "spirit", "deity", "saint",
                     "angel", "demon", "daemon", "myth", "folklore"}
        is_role_hint = paren_text.strip() in ok_hints or any(
            h in paren_text for h in ok_hints
        )
        if not is_role_hint:
            return False, "paren-disambiguator differs and is not a role hint"
        # Role-hint merges require at least one non-empty culture on BOTH
        # sides (else we'd merge "María" Filipino with "Maria (Mother of God)"
        # just because both happen to have no cultures set).
        if not (a.cultural_associations and b.cultural_associations):
            return False, "paren differs; one side has no culture to anchor"
        if not _cultures_overlap(a.cultural_associations, b.cultural_associations):
            return False, "paren differs; cultures disjoint"
        return True, f"role-hint paren merge (paren={paren_text!r})"

    # Both paren'd — only merge if cultures overlap AND disambiguators match
    if _has_paren(a.name) and _has_paren(b.name):
        if _norm_name(a.name) != _norm_name(b.name):
            return False, "both paren'd with different disambiguators"

    # Neither paren'd OR both paren'd identical: merge when cultures overlap
    # OR external IDs match OR both cultures are empty.
    if _external_ids_overlap(a.external_ids, b.external_ids):
        return True, "matching external_id"
    if _cultures_overlap(a.cultural_associations, b.cultural_associations):
        return True, "cultures overlap"
    if not (a.cultural_associations or b.cultural_associations):
        return True, "both cultures empty"
    return False, "cultures disjoint"


def _pick_survivor(a: Entity, b: Entity) -> tuple[Entity, Entity]:
    """Return (survivor, loser)."""
    ca = a.consensus_confidence or 0.0
    cb = b.consensus_confidence or 0.0
    if ca > cb:
        return a, b
    if cb > ca:
        return b, a
    return (a, b) if a.id < b.id else (b, a)


def merge_pair(session, survivor: Entity, loser: Entity) -> dict:
    """Perform the actual merge; returns a summary dict for the audit log."""
    before_survivor = {
        "alternate_names": dict(survivor.alternate_names or {}),
        "powers": list(survivor.powers or []),
        "domains": list(survivor.domains or []),
        "cultural_associations": list(survivor.cultural_associations or []),
        "geographical_associations": list(survivor.geographical_associations or []),
        "external_ids": dict(survivor.external_ids or {}),
        "provenance_sources": list(survivor.provenance_sources or []),
    }

    # Union the fields.
    survivor.alternate_names = _union_dict_lists(
        survivor.alternate_names, loser.alternate_names
    )
    survivor.powers = _union_list(survivor.powers, loser.powers)
    survivor.domains = _union_list(survivor.domains, loser.domains)
    survivor.cultural_associations = _union_list(
        survivor.cultural_associations, loser.cultural_associations
    )
    survivor.geographical_associations = _union_list(
        survivor.geographical_associations, loser.geographical_associations
    )
    survivor.provenance_sources = _union_list(
        survivor.provenance_sources, loser.provenance_sources
    )
    merged_ext = dict(survivor.external_ids or {})
    for k, v in (loser.external_ids or {}).items():
        if k not in merged_ext:
            merged_ext[k] = v
    survivor.external_ids = merged_ext

    # Pull any pre-existing description over if survivor has none.
    if not survivor.description and loser.description:
        survivor.description = loser.description

    # Re-point IngestedEntity rows toward the survivor's normalised name.
    # (We keep the extraction_name_normalized string; matching is by-name later.)
    session.execute(
        update(IngestedEntity)
        .where(IngestedEntity.entity_name_normalized.ilike(loser.name or ""))
        .values(entity_name_normalized=(survivor.name or ""))
    )

    # Move outgoing + incoming relationships onto the survivor. Skip self-loops.
    session.execute(
        update(EntityRelationship)
        .where(EntityRelationship.source_entity_id == loser.id)
        .where(EntityRelationship.target_entity_id != survivor.id)
        .values(source_entity_id=survivor.id)
    )
    session.execute(
        update(EntityRelationship)
        .where(EntityRelationship.target_entity_id == loser.id)
        .where(EntityRelationship.source_entity_id != survivor.id)
        .values(target_entity_id=survivor.id)
    )
    # Drop any leftover self-loops that the moves would have created.
    session.execute(
        EntityRelationship.__table__.delete()
        .where(EntityRelationship.source_entity_id == loser.id)
    )
    session.execute(
        EntityRelationship.__table__.delete()
        .where(EntityRelationship.target_entity_id == loser.id)
    )

    # Demote loser but DO NOT DELETE — keeps audit trail.
    loser.review_status = "merged"

    # Log audit row.
    session.add(ReviewAction(
        entity_id=loser.id,
        reviewer="dedupe-script",
        action="dedupe_merge",
        field=None,
        old_value={
            "loser_name": loser.name,
            "loser_conf": float(loser.consensus_confidence or 0),
        },
        new_value={
            "survivor_id": survivor.id,
            "survivor_name": survivor.name,
            "merged_at": datetime.now(timezone.utc).isoformat(),
        },
        note="Automatic dedup",
    ))

    return {
        "survivor_id": survivor.id,
        "survivor_name": survivor.name,
        "loser_id": loser.id,
        "loser_name": loser.name,
        "before_survivor": before_survivor,
    }


# Out-of-scope names to delete outright (Tier 4 that slipped through)
BLOCKED_NAMES = {
    "princess bubblegum",
    "harry potter",
    "slender man", "slenderman",
}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()

    groups = find_dup_groups()
    log.info("%d dup groups to evaluate", len(groups))

    merges: list[dict] = []
    skipped: list[tuple[str, str]] = []
    purged: list[dict] = []

    with get_db_session() as session:
        for key, group in groups.items():
            # Blocked-name purge first.
            if key in BLOCKED_NAMES:
                for e in group:
                    purged.append({"id": e.id, "name": e.name, "reason": "blocked name"})
                    if args.apply:
                        e.review_status = "out_of_scope"
                continue

            # Sort by confidence desc to pick the best survivor first.
            group = sorted(group, key=lambda x: -(x.consensus_confidence or 0))

            # Greedy pair-merge: each row tries to merge with the current survivor.
            survivor = group[0]
            # Re-fetch survivor to attach to session.
            survivor = session.merge(survivor)

            for candidate in group[1:]:
                candidate = session.merge(candidate)
                ok, reason = should_merge(survivor, candidate)
                if not ok:
                    skipped.append(
                        (f"{survivor.id}:{survivor.name} vs {candidate.id}:{candidate.name}", reason)
                    )
                    continue
                # Re-pick survivor in case candidate actually is stronger.
                new_survivor, loser = _pick_survivor(survivor, candidate)
                audit = merge_pair(session, new_survivor, loser)
                audit["reason"] = reason
                merges.append(audit)
                survivor = new_survivor

            if args.apply:
                session.commit()

    if args.apply:
        log.info("applied %d merges, skipped %d pairs, purged %d rows",
                 len(merges), len(skipped), len(purged))

    # Audit report.
    import time
    stamp = time.strftime("%Y%m%dT%H%M%S")
    from pathlib import Path
    audit_dir = Path("data")
    audit_dir.mkdir(exist_ok=True)
    audit_path = audit_dir / f"dedupe_audit_{stamp}.jsonl"
    with audit_path.open("w", encoding="utf-8") as fh:
        for m in merges:
            fh.write(json.dumps({"type": "merge", **m}, ensure_ascii=False, default=str) + "\n")
        for name, reason in skipped:
            fh.write(json.dumps({"type": "skip", "pair": name, "reason": reason},
                               ensure_ascii=False) + "\n")
        for p in purged:
            fh.write(json.dumps({"type": "purge", **p}, ensure_ascii=False) + "\n")
    log.info("audit → %s", audit_path)

    print(json.dumps({
        "dup_groups_seen": len(groups),
        "merges": len(merges),
        "skipped": len(skipped),
        "purged_rows": len(purged),
        "dry_run": not args.apply,
        "audit_file": str(audit_path),
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
