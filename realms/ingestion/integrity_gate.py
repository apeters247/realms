"""Stage 3 integrity gate: decide whether to accept, flag, or reject an extraction.

Combines the deterministic quote check (``verify_quote``) and the semantic
claim check (``verify_claim``) into a single per-extraction verdict, writes
an ``integrity_meta`` JSONB record, and returns the action the worker should take.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Iterable

from .verify_claim import verify_claim, Verdict
from .verify_quote import verify_quote

log = logging.getLogger(__name__)


class Action(str, Enum):
    ACCEPT = "accept"
    FLAG_FOR_REVIEW = "flag_for_review"
    REJECT = "reject"


@dataclass
class ClaimCheck:
    claim: str
    quote: str
    quote_present: bool           # Stage 1
    semantic_verdict: str         # Stage 2: supports | ambiguous | contradicts | skipped
    semantic_confidence: float
    verifier_model: str

    def is_supported(self, min_conf: float = 0.85) -> bool:
        return (
            self.quote_present
            and self.semantic_verdict in {"supports", "ambiguous"}
            and self.semantic_confidence >= min_conf
        )


@dataclass
class EntityIntegrity:
    entity_name: str
    checks: list[ClaimCheck]
    integrity_score: float
    action: Action

    def to_jsonb(self) -> dict:
        return {
            "entity_name": self.entity_name,
            "integrity_score": round(self.integrity_score, 4),
            "action": self.action.value,
            "checks": [asdict(c) for c in self.checks],
        }


def gather_claims(extracted: dict) -> list[tuple[str, str]]:
    """Return a list of (claim_sentence, quote) pairs for a single extracted entity.

    The extractor v4 emits one `quote_context` per entity, but every typed
    role field (parents, consorts, …) and the description are separate claims
    that reference that quote. We flatten them so each assertion gets its
    own verification.
    """
    name = extracted.get("name") or "(unnamed)"
    quote = extracted.get("quote_context") or ""
    claims: list[tuple[str, str]] = []

    desc = extracted.get("description")
    if desc:
        claims.append((f"{name}: {desc}", quote))

    role_fields = [
        "parents", "children", "consorts", "siblings",
        "teachers", "students", "servants", "serves",
        "enemies", "allies", "manifestations", "aspect_of",
        "syncretized_with", "created_by",
    ]
    for field in role_fields:
        values = extracted.get(field) or []
        for v in values:
            if isinstance(v, str) and v.strip():
                claims.append((f"{name} has a {field.rstrip('s')} named {v}", quote))

    fay = extracted.get("first_attested_year")
    if fay is not None:
        claims.append((f"{name} is first attested in year {fay}", quote))

    return claims


def run_gate(
    extracted: dict,
    source_chunk: str,
    *,
    accept_threshold: float = 0.99,
    flag_threshold: float = 0.90,
    semantic_min_conf: float = 0.85,
    skip_semantic_if_no_quote: bool = True,
) -> EntityIntegrity:
    """Run the integrity pipeline on one extracted entity.

    Args:
        extracted: raw dict from the extractor (one element of extractor's `entities`).
        source_chunk: the full text of the chunk the extraction came from.
        accept_threshold: entity-level score ≥ this → ACCEPT.
        flag_threshold: score ∈ [flag, accept) → FLAG_FOR_REVIEW; score < flag → REJECT.
        semantic_min_conf: per-claim verifier confidence required to count as "supported".
        skip_semantic_if_no_quote: if the deterministic check fails, don't pay for LLM.
    """
    claims = gather_claims(extracted)
    checks: list[ClaimCheck] = []

    if not claims:
        return EntityIntegrity(
            entity_name=extracted.get("name", ""),
            checks=[],
            integrity_score=0.0,
            action=Action.REJECT,
        )

    for claim, quote in claims:
        quote_ok = verify_quote(quote, source_chunk)
        if not quote_ok and skip_semantic_if_no_quote:
            checks.append(ClaimCheck(
                claim=claim[:400],
                quote=quote[:500],
                quote_present=False,
                semantic_verdict="skipped",
                semantic_confidence=0.0,
                verifier_model="",
            ))
            continue
        verdict = verify_claim(entity=extracted.get("name", ""), claim=claim, quote=quote)
        checks.append(ClaimCheck(
            claim=claim[:400],
            quote=quote[:500],
            quote_present=quote_ok,
            semantic_verdict=verdict.verdict,
            semantic_confidence=verdict.confidence,
            verifier_model=verdict.model,
        ))

    n = len(checks)
    supported = sum(1 for c in checks if c.is_supported(semantic_min_conf))
    score = supported / n if n else 0.0

    if score >= accept_threshold:
        action = Action.ACCEPT
    elif score >= flag_threshold:
        action = Action.FLAG_FOR_REVIEW
    else:
        action = Action.REJECT

    return EntityIntegrity(
        entity_name=extracted.get("name", ""),
        checks=checks,
        integrity_score=score,
        action=action,
    )


def batch_score(entities: Iterable[EntityIntegrity]) -> float:
    """Corpus-level score = sum(supported claims) / sum(total claims)."""
    supported = 0
    total = 0
    for e in entities:
        for c in e.checks:
            total += 1
            if c.is_supported():
                supported += 1
    return supported / total if total else 0.0
