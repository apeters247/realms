"""LLM-based entity extraction.

Backend is OpenRouter direct (not LiteLLM) to avoid proxy-level timeouts that
occurred when routing through the estimabio LiteLLM instance. This mirrors the
pair classifier, keeping a single LLM path for the whole pipeline.
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

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "extract_entities.md"
PROMPT_VERSION = "v4"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

ROLE_FIELDS: dict[str, tuple[str, bool]] = {
    "parents":          ("parent_of",        True),
    "children":         ("parent_of",        False),
    "consorts":         ("consort_of",       False),
    "siblings":         ("sibling_of",       False),
    "teachers":         ("teacher_of",       True),
    "students":         ("teacher_of",       False),
    "servants":         ("serves",           True),
    "serves":           ("serves",           False),
    "enemies":          ("enemy_of",         False),
    "allies":           ("allied_with",      False),
    "manifestations":   ("manifests_as",     False),
    "aspect_of":        ("aspect_of",        False),
    "syncretized_with": ("syncretized_with", False),
    "created_by":       ("created_by",       False),
}
DEFAULT_MODEL = os.getenv(
    "REALMS_EXTRACTION_MODEL",
    "anthropic/claude-sonnet-4.5",
)
FALLBACK_MODELS = [
    m.strip()
    for m in os.getenv(
        "REALMS_EXTRACTION_FALLBACK_MODELS",
        "deepseek/deepseek-chat,google/gemini-2.0-flash-001",
    ).split(",")
    if m.strip()
]
DEFAULT_TEMPERATURE = float(os.getenv("REALMS_EXTRACTION_TEMPERATURE", "0.1"))
MAX_RETRIES = int(os.getenv("REALMS_EXTRACTION_MAX_RETRIES", "3"))
RETRY_BASE_DELAY = float(os.getenv("REALMS_EXTRACTION_RETRY_DELAY", "2.0"))
REQUEST_TIMEOUT = int(os.getenv("REALMS_EXTRACTION_TIMEOUT", "120"))


@dataclass
class ExtractedEntity:
    name: str
    entity_type: str | None
    alignment: str | None
    realm: str | None
    description: str | None
    powers: list[str]
    domains: list[str]
    cultural_associations: list[str]
    geographical_associations: list[str]
    alternate_names: dict[str, list[str]]
    confidence: float
    quote_context: str
    roles: dict[str, list[str]]
    # v4 temporal fields (all optional; None when the source doesn't state a year)
    first_attested_year: int | None = None
    evidence_period_start: int | None = None
    evidence_period_end: int | None = None
    historical_notes: str | None = None


@dataclass
class ExtractionResult:
    entities: list[ExtractedEntity]
    raw_response: dict[str, Any]
    model: str
    temperature: float
    prompt_version: str


def _strip_json_fences(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def _parse_response(content: str) -> dict[str, Any]:
    cleaned = _strip_json_fences(content)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise


# Canonical enumerations. Anything outside these sets gets normalised to the
# nearest member, or set to None if nothing matches. This prevents the LLM
# from inventing types like "realm" / "mythical_creature" / "null".
ENTITY_TYPE_ENUM = {
    "angelic", "plant_spirit", "animal_ally", "ancestor",
    "deity", "demonic", "nature_spirit", "human_specialist",
}
ENTITY_TYPE_ALIASES = {
    "god": "deity", "goddess": "deity", "divinity": "deity",
    "spirit": "nature_spirit", "spirits": "nature_spirit",
    "spiritual_being": "nature_spirit",
    "animal_spirit": "animal_ally", "animal_allies": "animal_ally",
    "plant_being": "plant_spirit",
    "angel": "angelic", "archangel": "angelic",
    "demon": "demonic", "devil": "demonic", "fallen_angel": "demonic",
    "cryptid": "nature_spirit", "legendary_creature": "nature_spirit",
    "monster": "nature_spirit", "mythical_creature": "nature_spirit",
    "mythical": "nature_spirit", "mythological": "nature_spirit",
    "legendary": "nature_spirit",
    "saint": "ancestor", "martyr": "ancestor",
    "shaman": "human_specialist", "priest": "human_specialist",
    "priestess": "human_specialist", "prophet": "human_specialist",
    "guardian_spirit": "nature_spirit",
    "ghost": "ancestor",
    "realm": None,  # not a valid type; the LLM confused a *place* for an entity type
    "null": None, "none": None, "undefined": None, "unknown": None,
    "n/a": None, "": None,
}

ALIGNMENT_ENUM = {"beneficial", "neutral", "malevolent", "protective", "ambiguous"}
ALIGNMENT_ALIASES = {
    "good": "beneficial", "benign": "beneficial", "benevolent": "beneficial",
    "evil": "malevolent", "bad": "malevolent", "harmful": "malevolent",
    "guardian": "protective", "protector": "protective",
    "mixed": "ambiguous", "complex": "ambiguous", "dual": "ambiguous",
    "null": None, "none": None, "unknown": None, "": None,
}

REALM_ENUM = {
    "earth", "sky", "underworld", "water", "forest", "mountain",
    "hyperspace", "intermediate",
}
REALM_ALIASES = {
    "heaven": "sky", "heavens": "sky", "heavenly": "sky",
    "celestial": "sky", "cosmic": "sky",
    "hell": "underworld", "netherworld": "underworld", "afterworld": "underworld",
    "river": "water", "ocean": "water", "sea": "water", "lake": "water",
    "woods": "forest", "jungle": "forest", "woodland": "forest",
    "hill": "mountain", "mountainous": "mountain",
    "terrestrial": "earth", "ground": "earth",
    "middle": "intermediate", "between": "intermediate", "liminal": "intermediate",
    "null": None, "none": None, "unknown": None, "": None,
}


def _normalise_enum(raw: Any, enum: set[str], aliases: dict[str, Any]) -> str | None:
    """Map an LLM-emitted value to its canonical enum member, or None."""
    if raw is None:
        return None
    s = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    if not s or s in {"null", "none", "undefined", "unknown", "n/a"}:
        return None
    if s in enum:
        return s
    if s in aliases:
        return aliases[s]
    # Try suffix variants (e.g. "deities" → "deity")
    stripped = s.rstrip("s")
    if stripped in enum:
        return stripped
    if stripped in aliases:
        return aliases[stripped]
    # Unknown value — drop to None rather than persist a garbage string.
    return None


def _coerce_entity(raw: dict[str, Any]) -> ExtractedEntity | None:
    name = (raw.get("name") or "").strip()
    if not name:
        return None
    roles: dict[str, list[str]] = {}
    for field in ROLE_FIELDS:
        values = raw.get(field) or []
        if isinstance(values, str):
            values = [values]
        if isinstance(values, list):
            cleaned = [str(v).strip() for v in values if v and isinstance(v, (str, int))]
            cleaned = [v for v in cleaned if v]
            if cleaned:
                roles[field] = cleaned
    def _to_int(v: Any) -> int | None:
        if v is None or v == "":
            return None
        try:
            iv = int(v)
        except (TypeError, ValueError):
            return None
        # sanity clamp to historically-plausible CE range
        if iv < -3000 or iv > 2100:
            return None
        return iv

    return ExtractedEntity(
        name=name[:200],
        entity_type=_normalise_enum(raw.get("entity_type"), ENTITY_TYPE_ENUM, ENTITY_TYPE_ALIASES),
        alignment=_normalise_enum(raw.get("alignment"), ALIGNMENT_ENUM, ALIGNMENT_ALIASES),
        realm=_normalise_enum(raw.get("realm"), REALM_ENUM, REALM_ALIASES),
        description=(raw.get("description") or None),
        powers=list(raw.get("powers") or []),
        domains=list(raw.get("domains") or []),
        cultural_associations=list(raw.get("cultural_associations") or []),
        geographical_associations=list(raw.get("geographical_associations") or []),
        alternate_names=dict(raw.get("alternate_names") or {}),
        confidence=float(raw.get("confidence") or 0.5),
        quote_context=(raw.get("quote_context") or "")[:500],
        roles=roles,
        first_attested_year=_to_int(raw.get("first_attested_year")),
        evidence_period_start=_to_int(raw.get("evidence_period_start")),
        evidence_period_end=_to_int(raw.get("evidence_period_end")),
        historical_notes=(raw.get("historical_notes") or None),
    )


def _call_openrouter(model: str, prompt: str, temperature: float) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    body = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {
                "role": "system",
                "content": "You extract structured JSON entity records. Return only valid JSON.",
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
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                raise RuntimeError(f"OpenRouter {resp.status_code}: {resp.text[:200]}")
            if 400 <= resp.status_code < 500:
                resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return content or ""
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            sleep_s = RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
            log.warning("[%s] attempt %d/%d failed (%s); retrying in %.1fs",
                        model, attempt + 1, MAX_RETRIES, exc, sleep_s)
            time.sleep(sleep_s)
    raise last_exc if last_exc else RuntimeError("retry exhausted")


def extract_entities(
    chunk_text: str,
    source_name: str,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
) -> ExtractionResult:
    """Call the LLM to extract entities from a single text chunk.

    Tries ``model`` first; on persistent failure cycles through ``FALLBACK_MODELS``.
    """
    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    prompt = (
        prompt_template
        .replace("{{SOURCE_NAME}}", source_name)
        .replace("{{CHUNK_TEXT}}", chunk_text)
    )

    models_to_try: list[str] = [model]
    for fb in FALLBACK_MODELS:
        if fb not in models_to_try:
            models_to_try.append(fb)

    content = ""
    chosen_model = model
    last_exc: Exception | None = None
    for m in models_to_try:
        try:
            content = _call_openrouter(m, prompt, temperature)
            chosen_model = m
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            log.warning("Extractor model %s failed after retries: %s", m, exc)
            continue
    if not content:
        raise last_exc if last_exc else RuntimeError("all models failed")

    try:
        parsed = _parse_response(content)
    except json.JSONDecodeError as exc:
        log.warning("LLM returned unparseable JSON (len=%d): %s", len(content), exc)
        return ExtractionResult(
            entities=[],
            raw_response={"error": "unparseable", "content": content[:2000]},
            model=chosen_model,
            temperature=temperature,
            prompt_version=PROMPT_VERSION,
        )

    raw_entities = parsed.get("entities") or []
    entities = []
    for raw in raw_entities:
        if not isinstance(raw, dict):
            continue
        coerced = _coerce_entity(raw)
        if coerced is not None:
            entities.append(coerced)

    return ExtractionResult(
        entities=entities,
        raw_response=parsed,
        model=chosen_model,
        temperature=temperature,
        prompt_version=PROMPT_VERSION,
    )
