"""LLM-based entity extraction via LiteLLM (OpenAI-compatible API)."""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "extract_entities.md"
PROMPT_VERSION = "v1"
DEFAULT_MODEL = os.getenv(
    "REALMS_EXTRACTION_MODEL",
    "claude-haiku-4-5-20251001",
)
DEFAULT_TEMPERATURE = float(os.getenv("REALMS_EXTRACTION_TEMPERATURE", "0.1"))


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


@dataclass
class ExtractionResult:
    entities: list[ExtractedEntity]
    raw_response: dict[str, Any]
    model: str
    temperature: float
    prompt_version: str


def _build_client() -> OpenAI:
    base_url = os.getenv("LITELLM_API_BASE", "http://litellm:4000")
    api_key = os.getenv("LITELLM_MASTER_KEY") or os.getenv("OPENAI_API_KEY") or "sk-dummy"
    return OpenAI(base_url=base_url, api_key=api_key)


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


def _coerce_entity(raw: dict[str, Any]) -> ExtractedEntity | None:
    name = (raw.get("name") or "").strip()
    if not name:
        return None
    return ExtractedEntity(
        name=name[:200],
        entity_type=raw.get("entity_type"),
        alignment=raw.get("alignment"),
        realm=raw.get("realm"),
        description=(raw.get("description") or None),
        powers=list(raw.get("powers") or []),
        domains=list(raw.get("domains") or []),
        cultural_associations=list(raw.get("cultural_associations") or []),
        geographical_associations=list(raw.get("geographical_associations") or []),
        alternate_names=dict(raw.get("alternate_names") or {}),
        confidence=float(raw.get("confidence") or 0.5),
        quote_context=(raw.get("quote_context") or "")[:500],
    )


def extract_entities(
    chunk_text: str,
    source_name: str,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
) -> ExtractionResult:
    """Call the LLM to extract entities from a single text chunk."""
    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    prompt = (
        prompt_template
        .replace("{{SOURCE_NAME}}", source_name)
        .replace("{{CHUNK_TEXT}}", chunk_text)
    )

    client = _build_client()
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": "You extract structured JSON entity records. Return only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        timeout=120,
    )
    content = response.choices[0].message.content or ""

    try:
        parsed = _parse_response(content)
    except json.JSONDecodeError as exc:
        log.warning("LLM returned unparseable JSON (len=%d): %s", len(content), exc)
        return ExtractionResult(
            entities=[],
            raw_response={"error": "unparseable", "content": content[:2000]},
            model=model,
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
        model=model,
        temperature=temperature,
        prompt_version=PROMPT_VERSION,
    )
