"""Seed IngestionSource rows from Wikisource-hosted scholarly encyclopedias.

All targets are public-domain:
  - 1911 Encyclopædia Britannica — one of the best one-volume encyclopedias
    for classical pantheons + world religion; written by named scholars.
  - The Jewish Encyclopædia (1906) — best scholarly coverage of Hebrew
    bible and Talmudic entities.
  - Catholic Encyclopedia (1913) — every saint, Marian apparition,
    angelology, demonology article.

Each article has a Wikisource page at a predictable title prefix.
We list them via the ``allpages`` API (prefix-bounded) and insert a
pending IngestionSource per article that passes the entity-relevance
filter. Runs idempotently against existing URLs.

Usage:
  docker exec realms-api python -m scripts.seed_wikisource_encyclopedias --dry-run
  docker exec realms-api python -m scripts.seed_wikisource_encyclopedias
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import time
from dataclasses import dataclass

import requests
from sqlalchemy import select

from realms.models import IngestionSource
from realms.utils.database import get_db_session

log = logging.getLogger("realms.seed_wikisource")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


WIKISOURCE_API = "https://en.wikisource.org/w/api.php"
HEADERS = {
    "User-Agent": "realms-seeder/1 (+https://realms.cloud; PD encyclopedia use)",
}


@dataclass
class Work:
    key: str
    display: str
    prefix: str       # Wikisource title prefix — passed to ``allpages``
    year: int
    credibility: float


WORKS = [
    Work(
        key="britannica_1911",
        display="Encyclopædia Britannica, 11th ed.",
        prefix="1911 Encyclopædia Britannica/",
        year=1911,
        credibility=0.87,
    ),
    Work(
        key="jewish_encyclopedia_1906",
        display="Jewish Encyclopedia (1906)",
        prefix="Jewish Encyclopedia/",
        year=1906,
        credibility=0.88,
    ),
    Work(
        key="catholic_encyclopedia_1913",
        display="Catholic Encyclopedia (1913)",
        prefix="Catholic Encyclopedia (1913)/",
        year=1913,
        credibility=0.85,
    ),
]


# Entity-relevance filter: keep articles whose short title either has
# one of these religion/mythology keywords OR is a short proper noun.
KEEP = {
    "god", "goddess", "deity", "deities",
    "spirit", "demon", "angel", "archangel",
    "saint", "apostle", "prophet", "patriarch",
    "mary", "virgin", "our lady",
    "mythology", "pantheon", "religion",
    "oracle", "shrine", "nymph", "fairy", "dragon", "giant",
    "soul", "heaven", "hell", "underworld",
    "witch", "sorcery", "magic", "divination",
    "druid", "bard", "shaman",
    "rabbi", "priest", "priestess",
    "heresy", "sect",
    # Well-known names (short titles pass below, this is belt-and-braces)
    "apollo", "zeus", "hera", "athena", "artemis",
    "odin", "thor", "freyja", "baldr",
    "shiva", "vishnu", "brahma", "krishna",
    "osiris", "isis", "horus", "anubis",
    "baal", "astarte", "moloch",
    "buddha", "bodhisattva",
    "jesus", "christ", "moses", "abraham", "david",
}

SKIP = {
    "university", "college", "school",
    "parliament", "government",
    "war of", "battle of",
    "city of", "town of",
    "treaty", "act of",
    "philosophy of",
    "physics", "chemistry", "anatomy",
    "biography", "biographical",
    "geography", "geology",
    "mathematics",
    "cookery", "cooking",
    "agriculture", "horticulture",
    "railway", "navigation",
    "industry",
    "abbreviations", "contributor", "front matter",
    "preface", "index of",
    "classified list",
    "bibliography",
    "errata",
    "plates",
    "table of",
}


def _short_title(full: str) -> str:
    """Extract article-local title — 'Foo Bar/Baz' → 'Baz'."""
    return full.split("/")[-1]


def _is_entity_title(full: str) -> bool:
    short = _short_title(full).lower()
    if any(s in short for s in SKIP):
        return False
    if any(k in short for k in KEEP):
        return True
    # Short proper-noun titles pass (1-3 words, ≥3 chars, starts with a letter).
    words = short.split()
    if 1 <= len(words) <= 3 and len(short) >= 3 and short[0].isalpha():
        return True
    return False


def _api(params: dict, retries: int = 4) -> dict:
    p = {"format": "json", "formatversion": "2", **params}
    for i in range(retries):
        try:
            resp = requests.get(WIKISOURCE_API, params=p, headers=HEADERS, timeout=30)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise RuntimeError(str(resp.status_code))
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            if i == retries - 1:
                raise
            time.sleep(0.5 * (2 ** i) + random.uniform(0, 0.4))
    raise RuntimeError("retries exhausted")


def list_allpages(prefix: str, cap: int = 6000) -> list[str]:
    """Iterate the allpages API for ns=0 titles starting with ``prefix``."""
    titles: list[str] = []
    cont_token: dict | None = None
    while len(titles) < cap:
        params = {
            "action": "query",
            "list": "allpages",
            "apprefix": prefix,
            "apnamespace": "0",
            "aplimit": "500",
        }
        if cont_token:
            params.update(cont_token)
        try:
            data = _api(params)
        except Exception as exc:  # noqa: BLE001
            log.warning("allpages %r: %s", prefix, exc)
            break
        for p in data.get("query", {}).get("allpages", []):
            titles.append(p["title"])
            if len(titles) >= cap:
                break
        cont = data.get("continue")
        if not cont:
            break
        cont_token = cont
        time.sleep(0.1)
    return titles


def _url_for(title: str) -> str:
    return "https://en.wikisource.org/wiki/" + title.replace(" ", "_")


def seed(dry_run: bool, cap_per_work: int) -> dict:
    with get_db_session() as session:
        existing = {
            u.strip().lower()
            for u in session.execute(
                select(IngestionSource.url).where(IngestionSource.url.isnot(None))
            ).scalars().all() if u
        }

    total_new = 0
    per_work_counts: dict[str, dict] = {}
    for work in WORKS:
        log.info("listing %s", work.prefix)
        titles = list_allpages(work.prefix, cap=cap_per_work)
        keep = [t for t in titles if _is_entity_title(t)]
        log.info("%s: %d total pages / %d entity-like",
                 work.key, len(titles), len(keep))

        new_rows = []
        for t in keep:
            url = _url_for(t)
            if url.lower() in existing:
                continue
            existing.add(url.lower())
            new_rows.append((t, url))

        if dry_run:
            for t, u in new_rows[:15]:
                print(f"  [{work.key}] {_short_title(t):40s}  {u}")
            per_work_counts[work.key] = {"total": len(titles), "kept": len(keep), "new": len(new_rows)}
            total_new += len(new_rows)
            continue

        if not new_rows:
            per_work_counts[work.key] = {"total": len(titles), "kept": len(keep), "new": 0}
            continue

        with get_db_session() as session:
            for full, url in new_rows:
                short = _short_title(full)
                session.add(IngestionSource(
                    source_type="encyclopedia",
                    source_name=f"{short} ({work.display})",
                    url=url,
                    language="en",
                    publication_year=work.year,
                    ingestion_status="pending",
                    peer_reviewed=True,
                    credibility_score=work.credibility,
                    error_log=f"seeded from {work.key}",
                ))
            session.commit()
        per_work_counts[work.key] = {"total": len(titles), "kept": len(keep), "new": len(new_rows)}
        total_new += len(new_rows)
        log.info("%s: inserted %d", work.key, len(new_rows))

    return {
        "per_work": per_work_counts,
        "total_inserted": 0 if dry_run else total_new,
        "dry_run": dry_run,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--cap", type=int, default=6000,
                   help="max pages per encyclopedia")
    args = p.parse_args()
    summary = seed(dry_run=args.dry_run, cap_per_work=args.cap)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
