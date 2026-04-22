"""Batch-classify every co_occurs_with edge into a typed relationship.

Rotates across the 3 confirmed-working free-tier OpenRouter models to
dodge per-model rate limits:
  - nvidia/nemotron-3-super-120b-a12b:free
  - openai/gpt-oss-120b:free
  - z-ai/glm-4.5-air:free

Resume-safe: checkpoints the highest processed edge id to a file so a
killed run can pick up where it left off.

Skip fast path: before calling the LLM, we check whether the two entities
share at least one extraction chunk. If not (transitive co-occurrence
from a long walk), we skip with label=no_shared_context so the edge
stays co_occurs_with. This cuts the LLM spend on ~60-80% of edges.

Usage:
    # One-shot, all edges:
    docker exec -d realms-api python -m scripts.classify_all_cooccurrence

    # Shard across N parallel workers by modulo:
    docker exec -d realms-api python -m scripts.classify_all_cooccurrence --shard 0/4
    docker exec -d realms-api python -m scripts.classify_all_cooccurrence --shard 1/4
    ...

    # Limit for testing:
    docker exec realms-api python -m scripts.classify_all_cooccurrence --limit 100 --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from realms.models import Entity, EntityRelationship, IngestedEntity
from realms.utils.database import get_db_session

log = logging.getLogger("realms.classify_all")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
CHECKPOINT_DIR = Path("/app/data/classify_ckpt")
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

# Free-tier models ordered by capability (best first). The script tries
# each in order on every call; if the top tier is rate-limited, it falls
# back through the list. When the entire account hits its daily cap
# (2000/day "free-models-per-day-high-balance"), we stop cleanly and
# return partial stats rather than burn retries.
#
# Ranked by size × reasoning quality × JSON-output cleanness as of 2026-04.
FREE_MODELS = [
    # Tier 1 — 120B+, strongest free reasoners
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openai/gpt-oss-120b:free",
    "minimax/minimax-m2.5:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    # Tier 2 — 24-80B instruct-tuned
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "google/gemma-4-26b-a4b-it:free",
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
    "google/gemma-3-27b-it:free",
    # Tier 3 — small but reliable
    "z-ai/glm-4.5-air:free",
    "openai/gpt-oss-20b:free",
    "inclusionai/ling-2.6-flash:free",
    "arcee-ai/trinity-large-preview:free",
    "google/gemma-3-12b-it:free",
]

# Daily-cap error codes from OpenRouter. We detect these and stop the
# run cleanly so the checkpoint is preserved.
_DAILY_CAP_MARKERS = (
    "free-models-per-day",
    "daily-cap",
    "requests-per-day",
)

# Typed relationship labels we accept from the LLM. Anything else → leave
# the edge as co_occurs_with.
SEMANTIC_LABELS = {
    "syncretized_with", "equivalent_to", "cognate_of", "counterpart_of",
    "parent_of", "child_of", "consort_of", "sibling_of",
    "aspect_of", "manifests_as", "teacher_of", "student_of",
    "allied_with", "enemy_of", "serves", "served_by", "created_by",
}


PROMPT_TEMPLATE = """You are classifying the relationship between two named spiritual entities that appear together in a source text.

Entity A: {a_name}
  - culture(s): {a_culture}
  - type: {a_type}

Entity B: {b_name}
  - culture(s): {b_culture}
  - type: {b_type}

Source passages where both are mentioned:
{passages}

Pick the BEST SINGLE relationship from this list, based ONLY on what the passages say:
- syncretized_with   (identified with an equivalent deity/saint in a different tradition)
- equivalent_to      (two names for the same entity)
- cognate_of         (etymologically and functionally related across languages)
- parent_of          (A is a parent of B)
- child_of           (A is a child of B)
- consort_of         (spouse / divine partner, symmetric)
- sibling_of         (symmetric siblings)
- aspect_of          (A is a form/aspect of B)
- manifests_as       (A appears in the form of B)
- teacher_of         (A teaches/initiates B)
- student_of         (A is taught by B)
- allied_with        (co-combatants, companions, symmetric)
- enemy_of           (adversaries, symmetric)
- serves             (A serves B)
- served_by          (A is served by B)
- created_by         (A is created by B, one-time event)
- unknown            (no clear relationship in the passages — DEFAULT)

Respond strictly with a JSON object, no markdown fences, no prose:
{{"label": "...", "confidence": 0.00, "quote": "verbatim ≤150 chars from passages justifying the label"}}

If you are not confident (less than 0.70), return label="unknown".
"""


@dataclass
class Verdict:
    label: str
    confidence: float
    quote: str
    model: str


class DailyCapHit(RuntimeError):
    """Raised when OpenRouter returns the account-wide daily cap 429."""


def _call(model: str, prompt: str, retries: int = 2) -> Verdict | None:
    api_key = os.environ["OPENROUTER_API_KEY"]
    body = {
        "model": model,
        "temperature": 0.0,
        "max_tokens": 200,
        "messages": [
            {"role": "system", "content": "You respond with a single JSON object. No prose, no markdown."},
            {"role": "user", "content": prompt},
        ],
    }
    for attempt in range(retries + 1):
        try:
            r = requests.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://realms.cloud",
                    "X-Title": "REALMS pair classifier",
                },
                json=body,
                timeout=35,
            )
            if r.status_code == 429:
                # Distinguish per-minute (retry) from per-day (abort cleanly).
                body_text = r.text.lower()
                if any(m in body_text for m in _DAILY_CAP_MARKERS):
                    raise DailyCapHit(
                        f"daily cap hit on {model}; stop and retry after reset"
                    )
                raise RuntimeError(f"429 per-min on {model}")
            if r.status_code >= 500:
                raise RuntimeError(f"{r.status_code}")
            r.raise_for_status()
            content = (r.json()["choices"][0]["message"].get("content") or "").strip()
            m = re.search(r"\{[\s\S]*\}", content)
            if not m:
                return None
            try:
                obj = json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
            label = str(obj.get("label", "unknown")).strip().lower()
            if label not in SEMANTIC_LABELS and label != "unknown":
                label = "unknown"
            conf = float(obj.get("confidence", 0.0) or 0.0)
            quote = str(obj.get("quote", "") or "")[:200]
            return Verdict(label=label, confidence=max(0.0, min(1.0, conf)), quote=quote, model=model)
        except DailyCapHit:
            raise
        except Exception as exc:  # noqa: BLE001
            if attempt == retries:
                return None
            time.sleep(1.2 * (2 ** attempt) + random.uniform(0, 0.5))
    return None


def classify_pair_rotating(
    a: Entity, b: Entity, passages: list[str], models: list[str]
) -> Verdict | None:
    """Call models in round-robin until one returns a parseable verdict."""
    prompt = PROMPT_TEMPLATE.format(
        a_name=a.name,
        a_culture=", ".join((a.cultural_associations or ["?"])[:3]) if isinstance(a.cultural_associations, list) else "?",
        a_type=a.entity_type or "?",
        b_name=b.name,
        b_culture=", ".join((b.cultural_associations or ["?"])[:3]) if isinstance(b.cultural_associations, list) else "?",
        b_type=b.entity_type or "?",
        passages="\n".join(f'  {i+1}. "{p[:500]}"' for i, p in enumerate(passages[:3])),
    )
    # Try models in their configured order (best first). Only shuffle
    # within the top tier so load balances across Tier-1 without
    # demoting a good model to last. The daily-cap sentinel bubbles up.
    models_try = list(models)
    daily_cap_models = 0
    for m in models_try:
        try:
            v = _call(m, prompt)
        except DailyCapHit:
            daily_cap_models += 1
            continue
        if v is not None:
            return v
    if daily_cap_models == len(models_try):
        raise DailyCapHit("all configured models hit the daily cap")
    return None


def _shared_passages(session: Session, a_name: str, b_name: str, cap: int = 3) -> list[str]:
    """Find distinct extraction chunks where BOTH entities appear."""
    if not a_name or not b_name:
        return []
    a_rows = session.execute(
        select(IngestedEntity.source_id, IngestedEntity.extraction_context)
        .where(IngestedEntity.entity_name_normalized.ilike(a_name))
        .where(IngestedEntity.extraction_context.isnot(None))
        .limit(200)
    ).all()
    if not a_rows:
        return []
    a_map = {(src, ctx): ctx for src, ctx in a_rows if ctx}
    a_sources = {src for src, _ in a_rows}
    b_rows = session.execute(
        select(IngestedEntity.source_id, IngestedEntity.extraction_context)
        .where(IngestedEntity.entity_name_normalized.ilike(b_name))
        .where(IngestedEntity.source_id.in_(a_sources) if a_sources else IngestedEntity.id.is_(None))
        .limit(200)
    ).all()
    b_set = {(src, ctx) for src, ctx in b_rows if ctx}
    shared = [a_map[k] for k in (set(a_map.keys()) & b_set)]
    return shared[:cap]


def iter_edges(
    limit: int | None,
    shard: tuple[int, int] | None,
    start_after_id: int | None = None,
    cross_tradition_only: bool = False,
):
    """Yield co_occurs_with edge ids. When cross_tradition_only=True, pre-filter
    in SQL to edges whose endpoints have different primary cultural_associations.
    """
    with get_db_session() as session:
        # Guard a.cultural_associations + b.cultural_associations typing:
        # the array-0 access fails if any value is a scalar, so we only
        # compare when both are arrays.
        if cross_tradition_only:
            stmt_sql = """
                SELECT r.id FROM entity_relationships r
                JOIN entities a ON a.id = r.source_entity_id
                JOIN entities b ON b.id = r.target_entity_id
                WHERE r.relationship_type = 'co_occurs_with'
                  AND jsonb_typeof(a.cultural_associations) = 'array'
                  AND jsonb_typeof(b.cultural_associations) = 'array'
                  AND a.cultural_associations->>0 IS NOT NULL
                  AND b.cultural_associations->>0 IS NOT NULL
                  AND a.cultural_associations->>0 != b.cultural_associations->>0
                  AND a.review_status NOT IN ('merged','out_of_scope','rejected')
                  AND b.review_status NOT IN ('merged','out_of_scope','rejected')
            """
            params: dict = {}
            if start_after_id is not None:
                stmt_sql += " AND r.id > :start_after"
                params["start_after"] = start_after_id
            stmt_sql += " ORDER BY r.id ASC"
            if limit is not None:
                stmt_sql += " LIMIT :lim"
                params["lim"] = limit * (shard[1] if shard else 1)
            from sqlalchemy import text as _text
            ids = [r[0] for r in session.execute(_text(stmt_sql), params).all()]
        else:
            stmt = (
                select(EntityRelationship.id)
                .where(EntityRelationship.relationship_type == "co_occurs_with")
            )
            if start_after_id is not None:
                stmt = stmt.where(EntityRelationship.id > start_after_id)
            stmt = stmt.order_by(EntityRelationship.id.asc())
            if limit is not None:
                stmt = stmt.limit(limit * (shard[1] if shard else 1))
            ids = [r[0] for r in session.execute(stmt).all()]

    emitted = 0
    for eid in ids:
        if shard is not None:
            me, total = shard
            if eid % total != me:
                continue
        yield eid
        emitted += 1
        if limit is not None and emitted >= limit:
            return


def checkpoint_path(shard: tuple[int, int] | None) -> Path:
    if shard is None:
        return CHECKPOINT_DIR / "classify_all.last_id"
    return CHECKPOINT_DIR / f"classify_shard_{shard[0]}_of_{shard[1]}.last_id"


def load_checkpoint(ckpt: Path) -> int | None:
    if ckpt.exists():
        try:
            return int(ckpt.read_text().strip())
        except ValueError:
            return None
    return None


def save_checkpoint(ckpt: Path, eid: int) -> None:
    try:
        ckpt.write_text(str(eid))
    except OSError:
        pass


def run(
    limit: int | None, min_conf: float, dry_run: bool,
    shard: tuple[int, int] | None, resume: bool, sleep_ms: int,
    cross_tradition_only: bool = False,
) -> dict:
    ckpt = checkpoint_path(shard)
    start_after = load_checkpoint(ckpt) if resume else None
    if start_after is not None:
        log.info("resuming from edge id > %d", start_after)

    stats = {
        "scanned": 0, "no_passage": 0, "updated": 0,
        "skipped_low_conf": 0, "llm_fail": 0,
        "label_counts": {},
    }

    for eid in iter_edges(
        limit, shard, start_after_id=start_after,
        cross_tradition_only=cross_tradition_only,
    ):
        stats["scanned"] += 1
        with get_db_session() as session:
            edge = session.get(EntityRelationship, eid)
            if not edge or edge.relationship_type != "co_occurs_with":
                save_checkpoint(ckpt, eid)
                continue  # already classified by another worker or removed
            a = session.get(Entity, edge.source_entity_id)
            b = session.get(Entity, edge.target_entity_id)
            if a is None or b is None:
                save_checkpoint(ckpt, eid)
                continue
            if a.review_status in {"merged", "out_of_scope"} or b.review_status in {"merged", "out_of_scope"}:
                save_checkpoint(ckpt, eid)
                continue
            passages = _shared_passages(session, a.name, b.name, cap=3)

        if not passages:
            stats["no_passage"] += 1
            save_checkpoint(ckpt, eid)
            continue

        try:
            verdict = classify_pair_rotating(a, b, passages, FREE_MODELS)
        except DailyCapHit:
            log.info("daily cap hit; stopping cleanly with stats: %s", stats)
            stats["stopped_reason"] = "daily_cap"
            return stats
        if verdict is None:
            stats["llm_fail"] += 1
            # don't checkpoint — so a retry later can try again
            continue
        stats["label_counts"][verdict.label] = stats["label_counts"].get(verdict.label, 0) + 1

        if verdict.label == "unknown" or verdict.confidence < min_conf:
            stats["skipped_low_conf"] += 1
            save_checkpoint(ckpt, eid)
            continue

        if not dry_run:
            with get_db_session() as session:
                session.execute(
                    update(EntityRelationship)
                    .where(EntityRelationship.id == eid)
                    .values(
                        relationship_type=verdict.label,
                        description=verdict.quote or None,
                        extraction_confidence=max(
                            session.get(EntityRelationship, eid).extraction_confidence or 0,
                            verdict.confidence,
                        ),
                        strength="strong" if verdict.confidence >= 0.9 else "moderate",
                    )
                )
                session.commit()
            stats["updated"] += 1

        save_checkpoint(ckpt, eid)

        if stats["scanned"] % 25 == 0:
            log.info("progress: %s", stats)

        if sleep_ms:
            time.sleep(sleep_ms / 1000.0)

    log.info("FINAL: %s", stats)
    return stats


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--min-confidence", type=float, default=0.7)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--shard", type=str,
                   help="Shard selector, e.g. 0/4 to run 1 of 4 parallel workers by edge_id mod 4.")
    p.add_argument("--no-resume", action="store_true",
                   help="Ignore checkpoint; start from the oldest edge.")
    p.add_argument("--sleep-ms", type=int, default=3500,
                   help="Sleep between edges. 3500ms keeps us under 20 req/min free-tier.")
    p.add_argument("--cross-tradition-only", action="store_true",
                   help="Only classify edges whose endpoints are in different primary cultures.")
    args = p.parse_args()

    shard = None
    if args.shard:
        m, n = args.shard.split("/")
        shard = (int(m), int(n))
        if not (0 <= shard[0] < shard[1]):
            raise SystemExit(f"invalid shard: {args.shard}")

    summary = run(
        limit=args.limit, min_conf=args.min_confidence, dry_run=args.dry_run,
        shard=shard, resume=not args.no_resume, sleep_ms=args.sleep_ms,
        cross_tradition_only=args.cross_tradition_only,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
