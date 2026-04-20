"""Stream I oracle sampling — nightly integrity audit.

Draws a random sample of recent ingested entities, asks a top-tier model
(Claude Opus 4.x) to independently judge the support-level of each claim,
writes aggregate stats to the ``integrity_audits`` table.

Run via cron:
    0 3 * * *  docker exec realms-api python -m scripts.run_integrity_oracle --sample 20

Or manually for spot-checks:
    python -m scripts.run_integrity_oracle --sample 40 --days 7
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy import and_, select

from realms.ingestion.integrity_gate import gather_claims
from realms.ingestion.verify_quote import verify_quote
from realms.models import IngestedEntity, IntegrityAudit
from realms.utils.database import get_db_session

log = logging.getLogger("realms.integrity_oracle")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ORACLE_MODEL = os.getenv("REALMS_ORACLE_MODEL", "anthropic/claude-opus-4")
ORACLE_URL = "https://openrouter.ai/api/v1/chat/completions"
ORACLE_TIMEOUT = int(os.getenv("REALMS_ORACLE_TIMEOUT", "60"))

_PROMPT = """You are performing an independent quality audit of a factual claim.

Entity: {entity}
Claim being audited: {claim}
Source quote: "{quote}"
Source context (for background; do not overweight): "{context}"

Does the quote **from the source** establish the claim?

Reply with JSON only, no prose:
{{"verdict": "supports" | "ambiguous" | "contradicts", "confidence": 0.0}}

Rules:
- "supports": a careful reader would say the quote establishes the claim.
- "ambiguous": quote hints but doesn't decide either way.
- "contradicts": quote disagrees with or refutes the claim.
- confidence ∈ [0.0, 1.0].
"""


def _oracle_call(entity: str, claim: str, quote: str, context: str) -> tuple[str, float]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    prompt = _PROMPT.format(
        entity=entity[:120],
        claim=claim[:400],
        quote=quote[:500],
        context=context[:800],
    )
    resp = requests.post(
        ORACLE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://realms.org",
            "X-Title": "REALMS integrity oracle",
        },
        json={
            "model": ORACLE_MODEL,
            "temperature": 0.0,
            "messages": [
                {"role": "system",
                 "content": "You are an integrity auditor. Return exactly one JSON object."},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=ORACLE_TIMEOUT,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"] or ""
    # Locate a JSON object regardless of fence/prose.
    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"oracle returned no JSON: {content[:200]!r}")
    parsed = json.loads(content[start:end + 1])
    verdict = str(parsed.get("verdict", "")).lower().strip()
    if verdict not in {"supports", "ambiguous", "contradicts"}:
        verdict = "ambiguous"
    try:
        conf = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    return verdict, max(0.0, min(1.0, conf))


def sample_ingestions(days: int, sample_size: int):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with get_db_session() as session:
        stmt = select(IngestedEntity).where(
            and_(
                IngestedEntity.created_at >= cutoff,
                IngestedEntity.quote_context.isnot(None),
                IngestedEntity.extraction_context.isnot(None),
            )
        )
        rows = session.execute(stmt).scalars().all()
    if not rows:
        log.warning("no ingestions in last %d days", days)
        return []
    random.shuffle(rows)
    return rows[:sample_size]


def audit(days: int, sample_size: int, dry_run: bool = False) -> dict:
    samples = sample_ingestions(days=days, sample_size=sample_size)
    if not samples:
        return {"sampled": 0, "supported": 0, "ambiguous": 0, "contradicted": 0}

    n_supported = n_ambiguous = n_contradicted = 0
    detail: list[dict] = []

    for i, ext in enumerate(samples, 1):
        extracted_dict = ext.raw_extracted_data or {}
        claims = gather_claims(extracted_dict)
        if not claims:
            continue
        # Only audit the description claim (the richest signal), keep cost bounded.
        claim, quote = claims[0]
        context = ext.extraction_context or ""
        quote_ok = verify_quote(quote, context)
        try:
            verdict, conf = _oracle_call(
                entity=extracted_dict.get("name", ""),
                claim=claim,
                quote=quote,
                context=context,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("oracle call failed for #%d: %s", ext.id, exc)
            continue
        if verdict == "supports":
            n_supported += 1
        elif verdict == "ambiguous":
            n_ambiguous += 1
        else:
            n_contradicted += 1
        detail.append({
            "ext_id": ext.id,
            "entity_name": extracted_dict.get("name"),
            "claim": claim[:200],
            "quote": quote[:200],
            "quote_present": quote_ok,
            "verdict": verdict,
            "confidence": conf,
        })
        if i % 5 == 0:
            log.info("progress %d/%d (s=%d a=%d c=%d)",
                     i, len(samples), n_supported, n_ambiguous, n_contradicted)
        # Gentle pacing; oracle models have lower concurrency.
        time.sleep(0.5)

    total = n_supported + n_ambiguous + n_contradicted
    error_rate = n_contradicted / total if total else 0.0
    log.info("audit complete: sampled=%d supported=%d ambiguous=%d contradicted=%d error_rate=%.3f",
             total, n_supported, n_ambiguous, n_contradicted, error_rate)

    if dry_run:
        return {
            "sampled": total, "supported": n_supported,
            "ambiguous": n_ambiguous, "contradicted": n_contradicted,
            "error_rate": error_rate, "detail": detail,
        }

    with get_db_session() as session:
        row = IntegrityAudit(
            sample_size=total,
            n_supported=n_supported,
            n_ambiguous=n_ambiguous,
            n_contradicted=n_contradicted,
            oracle_model=ORACLE_MODEL,
            sample_ids=detail,
            notes=f"days={days}",
        )
        session.add(row)
        session.commit()
        log.info("wrote integrity_audit row id=%d", row.id)
    return {
        "sampled": total, "supported": n_supported,
        "ambiguous": n_ambiguous, "contradicted": n_contradicted,
        "error_rate": error_rate,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=1,
                   help="how many days of recent ingestions to draw from")
    p.add_argument("--sample", type=int, default=20,
                   help="sample size")
    p.add_argument("--dry-run", action="store_true",
                   help="don't write integrity_audits row")
    args = p.parse_args()

    summary = audit(days=args.days, sample_size=args.sample, dry_run=args.dry_run)
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
