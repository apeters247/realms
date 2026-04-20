"""Stage 2 integrity check: LLM-based semantic verification.

A cheap, single-shot call that asks an independent model: "Does this source
quote support this specific claim about this entity?"

Runs after the deterministic quote-presence check in ``verify_quote``.
Uses a different model than the extractor to avoid self-confirmation bias
(extractor = Claude Sonnet 4.5; verifier = Gemini 2.0 Flash by default).
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass
from typing import Any

import requests

log = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

VERIFIER_MODEL = os.getenv(
    "REALMS_VERIFIER_MODEL",
    "google/gemini-2.0-flash-001",
)
VERIFIER_FALLBACK = os.getenv(
    "REALMS_VERIFIER_FALLBACK",
    "deepseek/deepseek-chat",
)
VERIFIER_TEMPERATURE = float(os.getenv("REALMS_VERIFIER_TEMPERATURE", "0.0"))
VERIFIER_TIMEOUT = int(os.getenv("REALMS_VERIFIER_TIMEOUT", "30"))

_PROMPT = """You are verifying that a factual claim about an entity is supported by a quote from a source text.

Entity: {entity}
Claim: {claim}
Source quote: "{quote}"

Does the quote support the claim?

Reply with a single JSON object, no prose, no fences:
{{"verdict": "supports" | "ambiguous" | "contradicts", "confidence": 0.0}}

- "supports" means a competent reader would agree the quote establishes the claim.
- "ambiguous" means the quote hints at the claim but is not decisive.
- "contradicts" means the quote disagrees with or actively refutes the claim.
- confidence ∈ [0.0, 1.0].
"""


@dataclass
class Verdict:
    verdict: str  # supports | ambiguous | contradicts
    confidence: float
    model: str

    def is_acceptable(self, min_conf: float = 0.85) -> bool:
        return self.verdict in {"supports", "ambiguous"} and self.confidence >= min_conf


def _parse(content: str) -> dict[str, Any]:
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if not m:
        raise ValueError(f"no JSON object in response: {content[:200]!r}")
    return json.loads(m.group(0))


def _call(model: str, prompt: str) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    body = {
        "model": model,
        "temperature": VERIFIER_TEMPERATURE,
        "messages": [
            {
                "role": "system",
                "content": "You respond with a single JSON object. No prose, no markdown.",
            },
            {"role": "user", "content": prompt},
        ],
    }
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            resp = requests.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://realms.org",
                    "X-Title": "REALMS",
                },
                json=body,
                timeout=VERIFIER_TIMEOUT,
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                raise RuntimeError(f"verifier {resp.status_code}: {resp.text[:200]}")
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"] or ""
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            sleep_s = 1.5 * (2 ** attempt) + random.uniform(0, 0.5)
            log.debug("verifier %s attempt %d failed: %s", model, attempt + 1, exc)
            time.sleep(sleep_s)
    raise last_exc if last_exc else RuntimeError("verifier retries exhausted")


def verify_claim(entity: str, claim: str, quote: str) -> Verdict:
    prompt = _PROMPT.format(entity=entity[:120], claim=claim[:400], quote=quote[:500])
    for model in (VERIFIER_MODEL, VERIFIER_FALLBACK):
        try:
            raw = _call(model, prompt)
            parsed = _parse(raw)
            verdict = str(parsed.get("verdict", "")).lower().strip()
            if verdict not in {"supports", "ambiguous", "contradicts"}:
                verdict = "ambiguous"
            conf_raw = parsed.get("confidence", 0.0)
            try:
                conf = float(conf_raw)
            except (TypeError, ValueError):
                conf = 0.0
            conf = max(0.0, min(1.0, conf))
            return Verdict(verdict=verdict, confidence=conf, model=model)
        except Exception as exc:  # noqa: BLE001
            log.warning("verifier model %s failed: %s", model, exc)
            continue
    # Fail-safe: when both verifier models fail, treat as "ambiguous" with
    # low confidence so the gate will flag-for-review rather than accept blindly.
    return Verdict(verdict="ambiguous", confidence=0.0, model="fallback-none")
