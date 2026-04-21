"""Stream D — seed IngestionSource rows from Wikipedia category trees.

Usage:
    # preview without writing
    python -m scripts.seed_from_wikipedia_category --category "Deities by culture" --depth 3 --dry-run

    # actually seed
    python -m scripts.seed_from_wikipedia_category --category "Legendary creatures by region" --depth 3
    python -m scripts.seed_from_wikipedia_category --category "Nature spirits" --depth 2

Safeguards:
- Hard blocklist of category names (Tier 3/4) so DMT/UFO/New-age content
  never enters the queue.
- Skips non-article namespaces (templates, files, categories themselves).
- Dedups against existing IngestionSource.url values.
- `--max N` caps the number of URLs inserted per run (default 400).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import time
from collections import deque
from typing import Iterable

import requests
from sqlalchemy import select

from realms.models import IngestionSource
from realms.utils.database import get_db_session

log = logging.getLogger("realms.seed_wikicat")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


WIKI_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {
    "User-Agent": os.getenv(
        "REALMS_WIKIPEDIA_UA",
        "REALMS-knowledge-base/0.1 (+https://realms.org; research use)",
    ),
}


# Categories we refuse to walk into — Tier 3 (entheogenic visionary) and
# Tier 4 (modern occult, fiction, UFO).
BLOCKED_CATEGORIES = {
    # Tier 3
    "dmt experiences",
    "ayahuasca experiences",
    "psychedelic entities",
    "machine elves",
    # Tier 4
    "new religious movements",
    "chaos magic",
    "ceremonial magic",
    "thelema",
    "satanism",
    "fictional characters",
    "fictional deities",
    "ufo religions",
    "contactee",
    "tulpamancy",
    "slenderman",
    "creepypasta",
    # Neutral but out of scope
    "role-playing games",
    "video games",
    "television characters",
}


# Article titles that match any blocked keyword are rejected.
BLOCKED_ARTICLE_SUBSTR = {
    "creepypasta",
    "slenderman",
    "tulpa",
    "machine elves",
    "extraterrestrial",
    "ufo",
    "alien abduction",
    "chaos magic",
    "thelema",
    "crowley",
    "lavey",
}


def _get(params: dict) -> dict:
    p = {"format": "json", "formatversion": "2", **params}
    for attempt in range(4):
        try:
            resp = requests.get(WIKI_API, params=p, headers=HEADERS, timeout=30)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise RuntimeError(f"wiki {resp.status_code}")
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            delay = 0.8 * (2 ** attempt) + random.uniform(0, 0.5)
            log.warning("wiki API attempt %d failed (%s); retry in %.1fs",
                        attempt + 1, exc, delay)
            time.sleep(delay)
    raise RuntimeError("wiki API retries exhausted")


def _is_blocked_category(name: str) -> bool:
    n = name.lower().replace("category:", "").strip()
    return any(blocked in n for blocked in BLOCKED_CATEGORIES)


def _is_blocked_article(title: str) -> bool:
    t = title.lower()
    return any(s in t for s in BLOCKED_ARTICLE_SUBSTR)


def walk_category(root: str, max_depth: int = 3) -> Iterable[dict]:
    """BFS over category tree; yield {title, url} for each article (ns=0)."""
    root_cat = f"Category:{root}" if not root.lower().startswith("category:") else root
    visited_categories: set[str] = set()
    visited_articles: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(root_cat, 0)])

    while queue:
        cat, depth = queue.popleft()
        if cat in visited_categories:
            continue
        visited_categories.add(cat)
        if _is_blocked_category(cat):
            log.info("skip blocked category: %s", cat)
            continue
        log.info("walking %s (depth=%d, queue=%d)", cat, depth, len(queue))
        cont_token: dict | None = None
        while True:
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": cat,
                "cmlimit": "100",
                "cmnamespace": "0|14",  # 0 = article, 14 = subcategory
            }
            if cont_token:
                params.update(cont_token)
            data = _get(params)
            members = data.get("query", {}).get("categorymembers", [])
            for m in members:
                title = m["title"]
                ns = m.get("ns")
                if ns == 14:  # subcategory
                    if depth + 1 <= max_depth:
                        queue.append((title, depth + 1))
                elif ns == 0:
                    if title in visited_articles:
                        continue
                    if _is_blocked_article(title):
                        continue
                    visited_articles.add(title)
                    url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                    yield {"title": title, "url": url, "category": cat}
            cont = data.get("continue")
            if not cont:
                break
            cont_token = cont
            time.sleep(0.1)  # politeness


def seed(root: str, max_depth: int, cap: int, dry_run: bool) -> dict:
    seen_urls: set[str] = set()
    with get_db_session() as session:
        existing = session.execute(
            select(IngestionSource.url).where(IngestionSource.url.isnot(None))
        ).scalars().all()
        seen_urls.update(u for u in existing if u)

    new_rows = []
    for art in walk_category(root, max_depth=max_depth):
        if art["url"] in seen_urls:
            continue
        seen_urls.add(art["url"])
        new_rows.append(art)
        if len(new_rows) >= cap:
            break

    log.info("discovered %d new articles (cap=%d)", len(new_rows), cap)
    if dry_run:
        for r in new_rows[:30]:
            print(r)
        print(f"... ({len(new_rows)} total)")
        return {"discovered": len(new_rows), "inserted": 0}

    with get_db_session() as session:
        for r in new_rows:
            session.add(IngestionSource(
                source_type="wikipedia",
                source_name=r["title"],
                url=r["url"],
                language="en",
                ingestion_status="pending",
                credibility_score=0.75,
                peer_reviewed=False,
                error_log=f"seeded from {r['category']}",
            ))
        session.commit()
    log.info("inserted %d new ingestion_sources", len(new_rows))
    return {"discovered": len(new_rows), "inserted": len(new_rows)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--category", required=True,
                   help="root category name (e.g., 'Deities by culture')")
    p.add_argument("--depth", type=int, default=3, help="max BFS depth")
    p.add_argument("--max", type=int, default=400, help="cap per run")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    summary = seed(args.category, max_depth=args.depth, cap=args.max, dry_run=args.dry_run)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
