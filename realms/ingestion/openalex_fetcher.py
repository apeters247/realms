"""OpenAlex + Unpaywall enrichment fetcher.

For a given entity name + tradition we:
  1. Search OpenAlex for works mentioning the entity (title + abstract).
  2. Filter to open-access items with a recognisable journal concept or
     field = religion / anthropology / folklore.
  3. For the best N works: resolve an open-access URL via Unpaywall (if DOI)
     or OpenAlex's own ``best_oa_location``.
  4. Yield :class:`ScholarlyWork` dicts compatible with
     ``IngestionSource`` row inserts (source_type='journal').

All APIs are free. OpenAlex requires no auth; Unpaywall asks for a
``mailto`` in the query string as courtesy.
"""
from __future__ import annotations

import logging
import os
import random
import time
from dataclasses import dataclass, field
from typing import Iterable

import requests

log = logging.getLogger(__name__)

OPENALEX_URL = "https://api.openalex.org/works"
UNPAYWALL_URL = "https://api.unpaywall.org/v2"

POLITE_MAILTO = os.getenv("REALMS_CONTACT_EMAIL", "realms@example.org")


@dataclass
class ScholarlyWork:
    openalex_id: str
    title: str
    authors: list[str]
    publication_year: int | None
    doi: str | None
    journal: str | None
    oa_url: str | None
    abstract: str | None
    relevance_score: float
    concepts: list[str] = field(default_factory=list)

    @property
    def is_usable(self) -> bool:
        return bool(self.title) and self.publication_year is not None

    def to_source_row(self, entity_name: str) -> dict:
        """Shape a dict matching IngestionSource columns."""
        return {
            "source_type": "journal",
            "source_name": self.title[:500],
            "authors": [{"name": a} for a in self.authors[:6]],
            "publication_year": self.publication_year,
            "journal_or_venue": self.journal,
            "doi": self.doi,
            "url": self.oa_url or (f"https://doi.org/{self.doi}" if self.doi else None),
            "language": "en",
            "credibility_score": 0.88,
            "peer_reviewed": True,
            "ingestion_status": "pending" if self.oa_url else "completed",
            "error_log": (
                f"openalex enrichment for '{entity_name}'; "
                f"score={self.relevance_score:.2f}; "
                f"concepts={','.join(self.concepts[:3])}"
            )[:500],
        }


# ─── search ──────────────────────────────────────────────────────────────

# Concepts we prefer (OpenAlex concept IDs for religion / anthropology /
# folklore fields). These bias results toward the right literature.
# Source: https://api.openalex.org/concepts — the top-level Humanities
# concepts we care about.
PREFERRED_CONCEPTS = {
    "religion",
    "theology",
    "mythology",
    "anthropology",
    "folklore",
    "ancient history",
    "classical studies",
    "archaeology",
    "ethnology",
    "history",
}


def _api_get(url: str, params: dict | None = None, retries: int = 4) -> dict:
    params = params or {}
    # OpenAlex/Unpaywall both like a mailto for "polite pool".
    params.setdefault("mailto", POLITE_MAILTO)
    for attempt in range(retries):
        try:
            resp = requests.get(
                url, params=params, timeout=30,
                headers={"User-Agent": f"realms-enricher/1 (mailto:{POLITE_MAILTO})"},
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                raise RuntimeError(f"{resp.status_code}: {resp.text[:120]}")
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            if attempt == retries - 1:
                raise
            delay = (1.5 ** attempt) + random.uniform(0, 0.5)
            log.debug("retry %d after %s", attempt + 1, exc)
            time.sleep(delay)
    raise RuntimeError("retries exhausted")


def _reconstruct_abstract(inv: dict | None) -> str | None:
    """OpenAlex ships abstracts as inverted index. Reconstruct to plain text."""
    if not inv:
        return None
    positions: list[tuple[int, str]] = []
    for word, idxs in inv.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(w for _, w in positions)


def search_openalex(entity: str, tradition: str | None, per_entity: int = 5) -> list[ScholarlyWork]:
    """Return up to ``per_entity`` scholarly works about ``entity``.

    We search by title, then filter client-side for domain relevance so we
    don't burn a pathological amount of API time.
    """
    query_parts = [entity]
    if tradition:
        query_parts.append(tradition)
    q = " ".join(query_parts)

    try:
        payload = _api_get(OPENALEX_URL, {
            "search": q,
            "per-page": "25",
            "filter": "has_abstract:true,is_paratext:false",
            "sort": "relevance_score:desc",
        })
    except Exception as exc:  # noqa: BLE001
        log.warning("openalex search failed for %r: %s", entity, exc)
        return []

    out: list[ScholarlyWork] = []
    for item in payload.get("results", []):
        title = (item.get("title") or "").strip()
        if not title:
            continue
        concepts = [c.get("display_name", "").lower() for c in item.get("concepts") or []]
        if not any(
            p in c or c in p
            for p in PREFERRED_CONCEPTS for c in concepts
        ):
            continue  # skip bio/chem matches etc.

        authors = [
            a.get("author", {}).get("display_name", "")
            for a in item.get("authorships") or []
            if a.get("author", {}).get("display_name")
        ]
        abstract = _reconstruct_abstract(item.get("abstract_inverted_index"))

        doi = (item.get("doi") or "").replace("https://doi.org/", "") or None
        venue = (
            item.get("primary_location", {})
            .get("source", {}) or {}
        ).get("display_name")
        oa = item.get("best_oa_location") or {}
        oa_url = oa.get("pdf_url") or oa.get("landing_page_url")

        out.append(ScholarlyWork(
            openalex_id=item.get("id", ""),
            title=title,
            authors=[a for a in authors if a][:8],
            publication_year=item.get("publication_year"),
            doi=doi,
            journal=venue,
            oa_url=oa_url,
            abstract=abstract,
            relevance_score=float(item.get("relevance_score") or 0.0),
            concepts=concepts[:5],
        ))
        if len(out) >= per_entity:
            break
    return out


# ─── unpaywall — find legal free URL for a DOI ──────────────────────────

def unpaywall_lookup(doi: str) -> str | None:
    if not doi:
        return None
    try:
        payload = _api_get(f"{UNPAYWALL_URL}/{doi}")
    except Exception as exc:  # noqa: BLE001
        log.debug("unpaywall miss %s: %s", doi, exc)
        return None
    loc = payload.get("best_oa_location") or {}
    return loc.get("url_for_pdf") or loc.get("url") or None


def enrich_entity(entity_name: str, tradition: str | None, *, per_entity: int = 3) -> Iterable[dict]:
    """Yield ``IngestionSource``-shaped dicts to add for this entity."""
    works = search_openalex(entity_name, tradition, per_entity=per_entity * 2)
    added = 0
    for w in works:
        if not w.is_usable:
            continue
        if not w.oa_url and w.doi:
            w.oa_url = unpaywall_lookup(w.doi)
        yield w.to_source_row(entity_name)
        added += 1
        if added >= per_entity:
            break
