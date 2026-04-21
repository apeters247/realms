"""LLM-based miner for syncretism / equivalence phrases inside entity descriptions.

For every entity with ``consensus_confidence ≥ 0.8`` and a non-empty
description, scan for telltale syncretism phrases:

    "identified with X"
    "equivalent to X"
    "counterpart of X in <tradition>"
    "syncretized with X"
    "Roman/Catholic/Greek counterpart"
    "also known as X in <tradition>"
    "associated with X"  (weaker — skipped by default)

If at least one candidate is found, issue a short LLM call (free model,
one-shot) to extract which named entity is being equated and return the
structured pairing. Resolve the other-entity to a DB row; create a
``syncretized_with`` edge with confidence derived from the LLM.

Cheap: ~1 LLM call per ~10 entities (depends on text), uses free models.

Usage:
  docker exec realms-api python -m scripts.mine_syncretism --dry-run --limit 50
  docker exec -d realms-api python -m scripts.mine_syncretism --limit 5000
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import time
import unicodedata
from typing import Iterable

import requests
from sqlalchemy import and_, or_, select

from realms.models import Entity, EntityRelationship, ReviewAction
from realms.utils.database import get_db_session

log = logging.getLogger("realms.mine_syncretism")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MINER_MODEL = os.getenv("REALMS_MINER_MODEL", "openai/gpt-oss-120b:free")
MINER_FALLBACKS = [
    m for m in os.getenv(
        "REALMS_MINER_FALLBACKS",
        "nvidia/nemotron-3-super-120b-a12b:free,z-ai/glm-4.5-air:free",
    ).split(",") if m.strip()
]
POLITE_MAILTO = os.getenv("REALMS_CONTACT_EMAIL", "realms@example.org")


# Phrase patterns that suggest a syncretism claim
TELLTALE_PATTERNS = [
    r"\bidentified with\b",
    r"\bequivalent to\b",
    r"\bcounterpart\b",
    r"\bsyncretized with\b",
    r"\bsyncretised with\b",
    r"\bsame (?:as|entity as)\b",
    r"\bcognate with\b",
    r"\ba ?/? ?k ?\. ?a\. ",  # a.k.a.
    r"\bis the .* equivalent\b",
    r"\bis the .* counterpart\b",
    r"\bidentical with\b",
    r"\banalog ous? of\b",
    r"\banalogue of\b",
    r"\bassimilated to\b",
]
TELLTALE_RE = re.compile("|".join(TELLTALE_PATTERNS), re.IGNORECASE)


def _norm(s: str) -> str:
    nfd = unicodedata.normalize("NFD", s or "")
    no_dia = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", no_dia.lower().strip())


def _call_llm(entity_name: str, description: str) -> list[dict]:
    """Ask the LLM to list syncretism claims in the description.

    Returns a list of ``{other_name, relationship, confidence, tradition, quote}``.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    prompt = f"""Extract cross-tradition entity links from the description below.

Entity: {entity_name}
Description:
{description[:2400]}

Find every statement that links this entity to an entity from ANOTHER tradition or region. Examples:
  - "Zeus, Greek counterpart of the Roman Jupiter" → {{"other_name": "Jupiter", "tradition": "Roman"}}
  - "Yemoja, syncretized with Our Lady of Regla in Cuban Santería" → {{"other_name": "Our Lady of Regla", "tradition": "Catholic"}}
  - "Thoth, identified with the Greek Hermes" → {{"other_name": "Hermes", "tradition": "Greek"}}
  - "Astarte, cognate with the Sumerian Inanna" → {{"other_name": "Inanna", "tradition": "Sumerian"}}

Return a JSON array; each item must contain:
  other_name (string), relationship ("syncretized_with"|"equivalent_to"|"cognate_of"|"counterpart_of"),
  tradition (string, the OTHER entity's tradition), confidence (0..1), quote (verbatim ≤150 chars).

If no cross-tradition link is present return an empty array.
Output strictly a JSON array — no prose, no markdown fences.
"""

    body = {
        "model": MINER_MODEL,
        "temperature": 0.0,
        "max_tokens": 500,
        "messages": [
            {"role": "system",
             "content": "You return strictly a JSON array as described. No prose."},
            {"role": "user", "content": prompt},
        ],
    }
    last_exc = None
    for model in [MINER_MODEL] + MINER_FALLBACKS:
        body["model"] = model
        for attempt in range(3):
            try:
                resp = requests.post(
                    OPENROUTER_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://realms.cloud",
                        "X-Title": "REALMS syncretism miner",
                    },
                    json=body, timeout=45,
                )
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise RuntimeError(f"{resp.status_code}")
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"] or ""
                m = re.search(r"\[[\s\S]*\]", content)
                if not m:
                    return []
                try:
                    data = json.loads(m.group(0))
                except json.JSONDecodeError:
                    return []
                if not isinstance(data, list):
                    return []
                return [d for d in data if isinstance(d, dict) and d.get("other_name")]
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                time.sleep(0.6 * (2 ** attempt) + random.uniform(0, 0.3))
    log.debug("miner all fallbacks failed: %s", last_exc)
    return []


def _find_entity(session, name: str) -> Entity | None:
    row = session.execute(
        select(Entity).where(Entity.review_status != "merged")
        .where(Entity.name.ilike(name.strip()))
    ).scalars().first()
    if row:
        return row
    # Fuzzy match on normalised name
    n = _norm(name)
    rows = session.execute(
        select(Entity).where(Entity.review_status != "merged")
        .where(Entity.name.ilike(f"%{name.strip()[:40]}%"))
        .limit(20)
    ).scalars().all()
    for r in rows:
        if _norm(r.name) == n:
            return r
    return None


def _edge_exists(session, a_id: int, b_id: int, rel: str) -> bool:
    return session.execute(
        select(EntityRelationship).where(
            EntityRelationship.relationship_type == rel,
            or_(
                and_(
                    EntityRelationship.source_entity_id == a_id,
                    EntityRelationship.target_entity_id == b_id,
                ),
                and_(
                    EntityRelationship.source_entity_id == b_id,
                    EntityRelationship.target_entity_id == a_id,
                ),
            ),
        )
    ).scalars().first() is not None


def mine(limit: int | None, dry_run: bool, min_confidence: float = 0.8) -> dict:
    added_pairs = 0
    calls_made = 0
    llm_misses = 0
    unresolved = 0
    entities_scanned = 0

    with get_db_session() as session:
        candidates = session.execute(
            select(Entity.id, Entity.name, Entity.description)
            .where(Entity.consensus_confidence >= min_confidence)
            .where(Entity.description.isnot(None))
            .where(Entity.review_status != "merged")
            .order_by(Entity.consensus_confidence.desc())
        ).all()

    for row in candidates:
        if limit is not None and entities_scanned >= limit:
            break
        entities_scanned += 1
        desc = row.description or ""
        if not TELLTALE_RE.search(desc):
            continue
        calls_made += 1
        try:
            claims = _call_llm(row.name, desc)
        except Exception as exc:  # noqa: BLE001
            log.warning("llm %s: %s", row.name, exc)
            claims = []
        if not claims:
            llm_misses += 1
            continue
        for c in claims:
            other_name = (c.get("other_name") or "").strip()
            rel = (c.get("relationship") or "syncretized_with").strip().lower()
            conf = float(c.get("confidence") or 0.7)
            if rel not in {"syncretized_with", "equivalent_to", "cognate_of", "counterpart_of"}:
                rel = "syncretized_with"
            if conf < 0.5:
                continue
            with get_db_session() as session:
                b = _find_entity(session, other_name)
                if not b:
                    unresolved += 1
                    continue
                if b.id == row.id:
                    continue
                if _edge_exists(session, row.id, b.id, rel):
                    continue
                if dry_run:
                    added_pairs += 1
                    continue
                for s_id, t_id in ((row.id, b.id), (b.id, row.id)):
                    session.add(EntityRelationship(
                        source_entity_id=s_id,
                        target_entity_id=t_id,
                        relationship_type=rel,
                        description=f"mined:{c.get('quote','')[:140]}",
                        strength="strong" if conf >= 0.85 else "moderate",
                        extraction_confidence=conf,
                    ))
                session.add(ReviewAction(
                    entity_id=row.id,
                    reviewer="syncretism-miner",
                    action="syncretism_link",
                    field=None,
                    old_value=None,
                    new_value={
                        "other_entity_id": b.id,
                        "other_entity_name": b.name,
                        "source": "llm-mined",
                        "quote": c.get("quote", "")[:200],
                    },
                ))
                session.commit()
                added_pairs += 1

        if entities_scanned % 25 == 0:
            log.info("scanned %d  llm_calls=%d  pairs_found=%d",
                     entities_scanned, calls_made, added_pairs)
        time.sleep(0.2)

    return {
        "entities_scanned": entities_scanned,
        "llm_calls_made": calls_made,
        "llm_empty": llm_misses,
        "pairs_added": added_pairs,
        "edges_written": added_pairs * 2 if not dry_run else 0,
        "unresolved_targets": unresolved,
        "dry_run": dry_run,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None,
                   help="max entities to scan (default: all eligible)")
    p.add_argument("--min-confidence", type=float, default=0.8)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    summary = mine(limit=args.limit, dry_run=args.dry_run,
                   min_confidence=args.min_confidence)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
