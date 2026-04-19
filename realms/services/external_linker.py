"""External-database matchers for Phase 6.

Two matchers:

* WikidataMatcher — SPARQL query against https://query.wikidata.org against
  common mythology / religion P31 (instance-of) classes, filtered by name
  match. Returns candidates with Q-id, label, description, confidence.

* VIAFMatcher — Authority-file SRU query against https://viaf.org using the
  personalName index. Handy for historical figures who were later deified.

Both matchers are polite (sleep between calls) and side-effect free. The
linking decision (auto-accept vs queue for review) lives in
``scripts/link_external_ids.py``.
"""
from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Iterable

import requests

log = logging.getLogger(__name__)

USER_AGENT = "REALMS/1.0 (research; contact: realms-project) requests"

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
WIKIDATA_POLITE_DELAY = 1.2  # seconds between calls; public endpoint is shared

VIAF_SEARCH_URL = "https://viaf.org/viaf/search"
VIAF_POLITE_DELAY = 0.6


@dataclass
class ExternalCandidate:
    system: str
    external_id: str
    label: str
    description: str | None
    confidence: float
    raw: dict


# ---- Wikidata --------------------------------------------------------------

# Narrow P31 set to common mythology/religion classes. Keeps SPARQL cheap.
# Q178885 = deity; Q18611254 = spirit; Q193291 = mythological creature;
# Q178561 = legendary creature; Q17488404 = religious figure; Q8162436 = demon.
_WIKIDATA_MYTH_CLASSES = [
    "wd:Q178885",     # deity
    "wd:Q18611254",   # spirit
    "wd:Q193291",     # mythological creature
    "wd:Q178561",     # legendary creature
    "wd:Q17488404",   # religious figure
    "wd:Q8162436",    # demon
    "wd:Q14514600",   # ancestor
    "wd:Q24238356",   # mythical being
    "wd:Q11396544",   # theonym
]


def _build_wikidata_query(name: str, limit: int = 10) -> str:
    """SPARQL query for entities whose rdfs:label or skos:altLabel matches ``name``."""
    safe = name.replace('"', '\\"')
    classes = " ".join(_WIKIDATA_MYTH_CLASSES)
    return f"""
SELECT ?item ?itemLabel ?itemDescription WHERE {{
  VALUES ?class {{ {classes} }}
  ?item wdt:P31/wdt:P279* ?class.
  ?item rdfs:label|skos:altLabel "{safe}"@en.
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT {limit}
"""


class WikidataMatcher:
    def __init__(self, polite_delay: float = WIKIDATA_POLITE_DELAY):
        self._delay = polite_delay
        self._last_call: float = 0.0

    def _respect_delay(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)
        self._last_call = time.monotonic()

    def match(self, name: str, description: str | None = None, limit: int = 10) -> list[ExternalCandidate]:
        self._respect_delay()
        query = _build_wikidata_query(name, limit=limit)
        resp = requests.get(
            WIKIDATA_SPARQL_URL,
            params={"query": query, "format": "json"},
            headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
            timeout=30,
        )
        if resp.status_code == 429:
            raise RuntimeError("Wikidata rate-limited (429); back off")
        resp.raise_for_status()
        data = resp.json()
        bindings = (data.get("results") or {}).get("bindings") or []
        candidates: list[ExternalCandidate] = []
        needle = (description or "").lower()
        for b in bindings:
            iri = (b.get("item") or {}).get("value", "")
            qid = iri.rsplit("/", 1)[-1] if iri else ""
            if not qid:
                continue
            label = (b.get("itemLabel") or {}).get("value", qid)
            descr = (b.get("itemDescription") or {}).get("value")
            # Heuristic confidence: 0.80 base; +0.1 if description non-empty;
            # +0.1 if caller description shares any word >=4 chars with candidate
            conf = 0.80
            if descr:
                conf += 0.10
                if needle and any(
                    tok.lower() in descr.lower()
                    for tok in needle.split()
                    if len(tok) >= 4
                ):
                    conf += 0.10
            candidates.append(ExternalCandidate(
                system="wikidata",
                external_id=qid,
                label=label,
                description=descr,
                confidence=min(0.99, conf),
                raw=b,
            ))
        return candidates


# ---- VIAF ------------------------------------------------------------------

class VIAFMatcher:
    def __init__(self, polite_delay: float = VIAF_POLITE_DELAY):
        self._delay = polite_delay
        self._last_call: float = 0.0

    def _respect_delay(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)
        self._last_call = time.monotonic()

    def match(self, name: str, limit: int = 5) -> list[ExternalCandidate]:
        self._respect_delay()
        # VIAF SRU: index 'local.personalNames' returns personalized entities.
        # We ask for JSON via the httpAccept=application/json param.
        query = f'local.personalNames all "{name}"'
        resp = requests.get(
            VIAF_SEARCH_URL,
            params={
                "query": query,
                "maximumRecords": str(limit),
                "httpAccept": "application/json",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        if resp.status_code == 429:
            raise RuntimeError("VIAF rate-limited (429); back off")
        resp.raise_for_status()
        data = resp.json()
        records = (
            ((data.get("searchRetrieveResponse") or {}).get("records")) or []
        )
        candidates: list[ExternalCandidate] = []
        for rec in records:
            rd = ((rec.get("record") or {}).get("recordData")) or {}
            viaf_id = rd.get("viafID")
            if not viaf_id:
                continue
            heading = ""
            headings = (rd.get("mainHeadings") or {}).get("data") or []
            if isinstance(headings, list) and headings:
                heading = (headings[0].get("text") if isinstance(headings[0], dict) else str(headings[0])) or ""
            elif isinstance(headings, dict):
                heading = headings.get("text") or ""
            candidates.append(ExternalCandidate(
                system="viaf",
                external_id=str(viaf_id),
                label=heading or name,
                description=None,
                confidence=0.70,
                raw=rec,
            ))
        return candidates


# ---- Decision helper -------------------------------------------------------

def auto_accept_decision(
    candidates: list[ExternalCandidate],
    *,
    min_confidence: float = 0.85,
    gap_factor: float = 2.0,
) -> ExternalCandidate | None:
    """Auto-accept the top candidate iff it beats the threshold + gap test.

    Returns the accepted candidate, or ``None`` to mean "queue for review".
    """
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0] if candidates[0].confidence >= min_confidence else None
    top, second = sorted(candidates, key=lambda c: c.confidence, reverse=True)[:2]
    if top.confidence < min_confidence:
        return None
    if top.confidence < gap_factor * second.confidence:
        return None
    return top
