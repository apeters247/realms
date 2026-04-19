"""Pair-relationship classifier using OpenRouter directly (bypasses LiteLLM).

Built for cost-efficient iteration over the co_occurs_with edge set.
Default model: Google Gemini 2.0 Flash (~$0.22/M tokens combined).
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "classify_pair.md"
PROMPT_VERSION = "v1"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.getenv("REALMS_PAIR_MODEL", "google/gemini-2.0-flash-001")
FALLBACK_MODEL = os.getenv("REALMS_PAIR_FALLBACK", "deepseek/deepseek-chat")
MAX_RETRIES = int(os.getenv("REALMS_PAIR_MAX_RETRIES", "3"))
RETRY_BASE_DELAY = float(os.getenv("REALMS_PAIR_RETRY_DELAY", "1.5"))

VALID_LABELS = {
    "parent_of", "child_of", "consort_of", "sibling_of", "allied_with",
    "enemy_of", "teacher_of", "student_of", "serves", "ruled_by",
    "manifests_as", "aspect_of", "syncretized_with", "created_by",
    "associated_with", "unknown",
}


@dataclass
class ClassificationResult:
    label: str
    confidence: float
    quote: str
    model: str
    raw: dict[str, Any]


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


def _call_openrouter(model: str, prompt: str, *, max_tokens: int = 300) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    body = {
        "model": model,
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You classify the relationship between two named entities based on "
                    "source text. Return only a single JSON object."
                ),
            },
            {"role": "user", "content": prompt},
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
                timeout=90,
            )
            if resp.status_code >= 500 or resp.status_code == 429:
                raise RuntimeError(f"OpenRouter {resp.status_code}: {resp.text[:200]}")
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return content or ""
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            sleep_s = RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
            log.warning("[%s] attempt %d/%d failed (%s); retrying in %.1fs",
                        model, attempt + 1, MAX_RETRIES, exc, sleep_s)
            time.sleep(sleep_s)
    raise last_exc or RuntimeError("openrouter retries exhausted")


def classify_pair(name_a: str, name_b: str, passages: list[str]) -> ClassificationResult:
    """Classify the relationship between two entities given co-occurring text.

    Returns a ClassificationResult. Falls back to FALLBACK_MODEL if the primary
    raises persistently.
    """
    if not passages:
        return ClassificationResult(
            label="unknown", confidence=0.0, quote="",
            model="none", raw={"note": "no passages"},
        )

    # Cap each passage + total size to keep costs predictable
    MAX_CHARS_PER = 2000
    MAX_TOTAL = 6000
    trimmed = []
    total = 0
    for p in passages:
        snippet = p[:MAX_CHARS_PER]
        if total + len(snippet) > MAX_TOTAL:
            break
        trimmed.append(snippet)
        total += len(snippet)

    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    prompt = (
        prompt_template
        .replace("{{NAME_A}}", name_a)
        .replace("{{NAME_B}}", name_b)
        .replace("{{PASSAGES}}", "\n\n---\n\n".join(trimmed))
    )

    last_exc: Exception | None = None
    for m in (DEFAULT_MODEL, FALLBACK_MODEL):
        try:
            content = _call_openrouter(m, prompt)
            parsed = _parse_json(content)
            label = str(parsed.get("label") or "unknown").strip().lower()
            if label not in VALID_LABELS:
                log.warning("Model returned invalid label %r, coercing to unknown", label)
                label = "unknown"
            confidence = float(parsed.get("confidence") or 0.0)
            confidence = max(0.0, min(1.0, confidence))
            quote = str(parsed.get("quote") or "")[:500]
            return ClassificationResult(
                label=label,
                confidence=confidence,
                quote=quote,
                model=m,
                raw=parsed,
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            log.warning("Classifier %s failed for (%r, %r): %s", m, name_a, name_b, exc)
            continue

    log.error("All classifier models failed for (%r, %r): %s", name_a, name_b, last_exc)
    return ClassificationResult(
        label="unknown", confidence=0.0, quote="",
        model="failed",
        raw={"error": str(last_exc) if last_exc else "unknown"},
    )
