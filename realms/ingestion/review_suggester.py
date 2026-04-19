"""LLM-assisted review suggestions.

Given an entity and all its raw extractions, asks an LLM to propose field-level
corrections. Uses the same OpenRouter-direct path as the extractor and the pair
classifier.
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
DEFAULT_MODEL = os.getenv("REALMS_REVIEW_MODEL", "google/gemini-2.0-flash-001")
FALLBACK_MODEL = os.getenv("REALMS_REVIEW_FALLBACK", "deepseek/deepseek-chat")
MAX_RETRIES = int(os.getenv("REALMS_REVIEW_MAX_RETRIES", "3"))
RETRY_BASE_DELAY = float(os.getenv("REALMS_REVIEW_RETRY_DELAY", "1.5"))


@dataclass
class Suggestion:
    suggested_fields: dict[str, Any]
    conflicts_detected: list[str]
    confidence: float
    rationale: str
    model: str
    raw: dict[str, Any]


_SYSTEM_PROMPT = (
    "You are reviewing an automatically-extracted entry in a spiritual-entity "
    "knowledge base. Given the current consensus row plus per-source extractions, "
    "propose corrections only where the evidence is clear. Return only a single "
    "JSON object with keys: suggested_fields (dict), conflicts_detected (list of "
    "field names where sources disagree), confidence (0-1), rationale (1-3 sentences)."
)


def _strip_fences(s: str) -> str:
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", s, re.DOTALL)
    if m:
        return m.group(1).strip()
    return s.strip()


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = _strip_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise


def _call_openrouter(model: str, user_prompt: str) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    body = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 600,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
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
                timeout=60,
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                raise RuntimeError(f"OpenRouter {resp.status_code}: {resp.text[:200]}")
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"] or ""
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5))
    raise last_exc or RuntimeError("openrouter retries exhausted")


def suggest_for_entity(entity_row: dict[str, Any], extractions: list[dict[str, Any]]) -> Suggestion:
    """Return field-level suggestions for ``entity_row`` given its extractions.

    ``entity_row`` is a dict snapshot of the Entity (name, entity_type, alignment, realm,
    description, powers, domains). ``extractions`` is a list of raw extraction dicts.
    """
    payload = {
        "current_consensus": entity_row,
        "per_source_extractions": extractions[:20],  # cap to keep prompt size sane
    }
    user_prompt = (
        "Here is the current consensus row and per-source extractions for one entity.\n"
        f"{json.dumps(payload, ensure_ascii=False)[:8000]}\n\n"
        "Return JSON only."
    )

    last_exc: Exception | None = None
    for m in (DEFAULT_MODEL, FALLBACK_MODEL):
        try:
            content = _call_openrouter(m, user_prompt)
            parsed = _parse_json(content)
            return Suggestion(
                suggested_fields=dict(parsed.get("suggested_fields") or {}),
                conflicts_detected=list(parsed.get("conflicts_detected") or []),
                confidence=max(0.0, min(1.0, float(parsed.get("confidence") or 0.0))),
                rationale=str(parsed.get("rationale") or "")[:1000],
                model=m,
                raw=parsed,
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            log.warning("review suggester %s failed: %s", m, exc)
            continue
    raise last_exc or RuntimeError("all suggester models failed")
