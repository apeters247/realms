# REALMS Data Quality + Phenomenological Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean existing data and tighten the REALMS ingestion pipeline to the phenomenological scope (pre-20th-century attested entities only): purge fictional pop-culture entities, calibrate LLM confidence scoring, merge duplicates, audit zero-extraction rate, enable the integrity gate, and backfill low-confidence entities with Brave-discovered sources.

**Architecture:** Five targeted changes to existing scripts/config — no new services or models. Scripts follow the existing `--apply` / dry-run pattern from `purge_hallucinations.py`. All commands run inside the `realms-api` container via `docker compose exec`.

**Tech Stack:** Python 3.11, SQLAlchemy, PostgreSQL 15 (pg_trgm already installed), Brave Search API, existing `realms.ingestion.*` modules.

---

## Prerequisites

Add `BRAVE_API_KEY` to `/var/www/realms/.env` (get from https://api.search.brave.com/app/keys):
```
BRAVE_API_KEY=BSA...
```

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `scripts/purge_fictional_entities.py` | Create | Delete entities whose description reveals fictional/media origin |
| `tests/test_purge_fictional.py` | Create | Integration tests for purge logic |
| `realms/ingestion/prompts/extract_entities.md` | Modify | Replace vague confidence rule with calibration table |
| `realms/ingestion/extractor.py` | Modify | Bump PROMPT_VERSION v4 → v5 |
| `realms/ingestion/normalizer.py` | Modify | Replace O(n) full-scan fuzzy match with trigram similarity query |
| `tests/test_normalizer.py` | Create | Test trigram-backed dedup in _find_existing |
| `realms/ingestion/worker.py` | Modify | Expand `_REL_KEYWORDS` with phenomenological encounter terms |
| `docker-compose.yml` | Modify | Enable integrity gate on all 4 ingestor containers |
| `scripts/backfill_integrity_and_sources.py` | Create | Integrity gate + Brave source discovery for confidence=0.4 entities |
| `tests/test_backfill_integrity.py` | Create | Unit tests for Brave search and integrity check helpers |

---

## Task 1: Fictional Entity Purge Script

**Files:**
- Create: `scripts/purge_fictional_entities.py`
- Create: `tests/test_purge_fictional.py`

### Step 1.1: Write the failing test

```python
# tests/test_purge_fictional.py
import pytest
from sqlalchemy import select
from realms.models import Entity, EntityRelationship, IngestedEntity, IngestionSource
from scripts.purge_fictional_entities import find_fictional_entities, purge_entities

pytestmark = pytest.mark.integration


@pytest.fixture()
def fictional_entity(db_session, seeded_source):
    """An entity whose description marks it as a fictional Marvel character."""
    e = Entity(
        name="Iron Fist",
        description="Iron Fist is a fictional character appearing in Marvel Comics.",
        consensus_confidence=0.8,
        provenance_sources=[seeded_source],
        extraction_instances=[],
    )
    db_session.add(e)
    db_session.flush()
    return e


@pytest.fixture()
def real_entity(db_session, seeded_source):
    """A legitimate mythological entity that must survive the purge."""
    e = Entity(
        name="Ogoun",
        description="Ogoun is the Yoruba and Vodou spirit of iron, warfare, and labour.",
        consensus_confidence=0.8,
        provenance_sources=[seeded_source],
        extraction_instances=[],
    )
    db_session.add(e)
    db_session.flush()
    return e


@pytest.fixture()
def seeded_source(db_session):
    s = IngestionSource(source_type="wikipedia", source_name="test", url="https://example.com",
                        ingestion_status="completed")
    db_session.add(s)
    db_session.flush()
    return s.id


def test_find_fictional_entities_matches_marvel(db_session, fictional_entity, real_entity):
    matches = find_fictional_entities(db_session)
    ids = [m[0] for m in matches]
    assert fictional_entity.id in ids
    assert real_entity.id not in ids


def test_find_fictional_entities_returns_signal(db_session, fictional_entity):
    matches = find_fictional_entities(db_session)
    match = next(m for m in matches if m[0] == fictional_entity.id)
    assert "marvel comics" in match[2].lower()  # (id, name, signal)


def test_purge_entities_deletes_fictional(db_session, fictional_entity, real_entity):
    purge_entities(db_session, [fictional_entity.id])
    db_session.commit()
    survivor = db_session.execute(
        select(Entity).where(Entity.id == real_entity.id)
    ).scalar_one_or_none()
    deleted = db_session.execute(
        select(Entity).where(Entity.id == fictional_entity.id)
    ).scalar_one_or_none()
    assert survivor is not None
    assert deleted is None


def test_purge_entities_cascades_relationships(db_session, fictional_entity, real_entity):
    rel = EntityRelationship(
        source_entity_id=fictional_entity.id,
        target_entity_id=real_entity.id,
        relationship_type="allied_with",
        strength="weak",
        extraction_confidence=0.5,
    )
    db_session.add(rel)
    db_session.flush()
    purge_entities(db_session, [fictional_entity.id])
    db_session.commit()
    remaining = db_session.execute(
        select(EntityRelationship).where(
            (EntityRelationship.source_entity_id == fictional_entity.id) |
            (EntityRelationship.target_entity_id == fictional_entity.id)
        )
    ).scalars().all()
    assert len(remaining) == 0
```

- [ ] **Step 1.2: Run tests to confirm they fail**

```bash
cd /var/www/realms && docker compose exec -T realms-api pytest tests/test_purge_fictional.py -v 2>&1 | head -30
```
Expected: `ImportError: cannot import name 'find_fictional_entities'`

- [ ] **Step 1.3: Implement the purge script**

```python
# scripts/purge_fictional_entities.py
"""Delete entities whose description reveals fictional/entertainment origin.

Complements purge_hallucinations.py (which checks cultural_associations).
This script checks the description field for unambiguous fictional media signals.

Usage:
    docker exec realms-api python -m scripts.purge_fictional_entities
    docker exec realms-api python -m scripts.purge_fictional_entities --apply
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from realms.models import Entity, EntityRelationship, IngestedEntity
from realms.utils.database import get_db_session

log = logging.getLogger("realms.purge_fictional")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

FICTIONAL_SIGNALS = [
    "fictional character",
    "fictional group",
    "fictional being",
    "marvel comics",
    "dc comics",
    "abs-cbn",
    "telefantasya",
    "silicon knights",
    "comic book",
    "video game",
    "animated series",
    "television series",
    "novel by",
    "film by",
    "movie character",
]


def find_fictional_entities(session: Session) -> list[tuple[int, str, str]]:
    """Return list of (entity_id, name, matched_signal) for fictional entities."""
    entities = session.execute(select(Entity).where(Entity.description.isnot(None))).scalars().all()
    matches = []
    for e in entities:
        desc = (e.description or "").lower()
        for signal in FICTIONAL_SIGNALS:
            if signal in desc:
                matches.append((e.id, e.name, signal))
                break
    return matches


def purge_entities(session: Session, entity_ids: list[int]) -> dict:
    """Delete entities and cascade to relationships and ingested_entities."""
    if not entity_ids:
        return {"entities": 0, "relationships": 0, "extractions": 0}

    rel_result = session.execute(
        delete(EntityRelationship).where(
            (EntityRelationship.source_entity_id.in_(entity_ids)) |
            (EntityRelationship.target_entity_id.in_(entity_ids))
        )
    )
    ext_result = session.execute(
        delete(IngestedEntity).where(
            IngestedEntity.entity_name_normalized.in_(
                session.execute(
                    select(Entity.name).where(Entity.id.in_(entity_ids))
                ).scalars().all()
            )
        )
    )
    ent_result = session.execute(
        delete(Entity).where(Entity.id.in_(entity_ids))
    )
    return {
        "entities": ent_result.rowcount,
        "relationships": rel_result.rowcount,
        "extractions": ext_result.rowcount,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually delete (default: dry-run)")
    args = parser.parse_args()

    with get_db_session() as session:
        matches = find_fictional_entities(session)
        log.info("Found %d fictional entities", len(matches))
        for eid, name, signal in matches:
            log.info("  [%d] %r → matched signal: %r", eid, name, signal)

        if not args.apply:
            log.info("Dry-run mode — pass --apply to delete")
            return

        entity_ids = [m[0] for m in matches]
        counts = purge_entities(session, entity_ids)
        session.commit()
        log.info(
            "Purged: %d entities, %d relationships, %d extractions",
            counts["entities"], counts["relationships"], counts["extractions"],
        )


if __name__ == "__main__":
    main()
```

- [ ] **Step 1.4: Run tests to confirm they pass**

```bash
cd /var/www/realms && docker compose exec -T realms-api pytest tests/test_purge_fictional.py -v 2>&1
```
Expected: All 4 tests PASS.

- [ ] **Step 1.5: Dry-run against live DB**

```bash
cd /var/www/realms && docker compose exec -T realms-api python -m scripts.purge_fictional_entities 2>&1
```
Expected: ~104 entities listed with their matched signal, "Dry-run mode" at end.

- [ ] **Step 1.6: Apply purge**

```bash
cd /var/www/realms && docker compose exec -T realms-api python -m scripts.purge_fictional_entities --apply 2>&1
```
Expected: "Purged: ~104 entities, ~200-400 relationships, ~150 extractions"

- [ ] **Step 1.7: Verify clean**

```bash
cd /var/www/realms && docker compose exec -T realms-api python3 -c "
import psycopg2, os
conn = psycopg2.connect(host=os.getenv('POSTGRES_HOST','localhost'), port=int(os.getenv('POSTGRES_PORT',5432)), user=os.getenv('POSTGRES_USER','realms'), password=os.getenv('POSTGRES_PASSWORD'), dbname=os.getenv('POSTGRES_DB','realms'))
cur = conn.cursor()
cur.execute(\"SELECT COUNT(*) FROM entities WHERE description ILIKE '%marvel comics%' OR description ILIKE '%fictional character%' OR description ILIKE '%dc comics%'\")
print('Remaining fictional entities:', cur.fetchone()[0])
conn.close()
" 2>/dev/null
```
Expected: `Remaining fictional entities: 0`

- [ ] **Step 1.8: Commit**

```bash
cd /var/www/realms
git add scripts/purge_fictional_entities.py tests/test_purge_fictional.py
git commit -m "feat: purge fictional/pop-culture entities from corpus"
```

---

## Task 2: Extraction Prompt Calibration (v5)

**Files:**
- Modify: `realms/ingestion/prompts/extract_entities.md` (rule 5 only)
- Modify: `realms/ingestion/extractor.py` (PROMPT_VERSION constant)

- [ ] **Step 2.1: Update rule 5 in the prompt**

Open `realms/ingestion/prompts/extract_entities.md`. Find and replace rule 5 (lines ~31-32):

Old:
```
5. `confidence` 0.0–1.0: 0.9+ for direct named descriptions, 0.6–0.8 for passing mentions.
```

New (replace the entire rule 5 line):
```
5. `confidence` — use the scale below. Match to the closest example. Do NOT default to 0.9.

   | Score | When to use | Example from text |
   |-------|-------------|-------------------|
   | 0.95  | Named entity with first-person encounter account or primary ritual text | "The shaman described meeting Ayahuasca Madre face-to-face during the ceremony…" |
   | 0.80  | Full paragraph with name, attributes, domain, and cultural role | "Tlaloc is the Aztec god of rain, lightning, and earthly fertility, worshipped since at least 200 BCE…" |
   | 0.65  | Named with partial description or a single attribute stated | "…accompanied by Huitzilopochtli, the sun god" |
   | 0.40  | Passing mention, list entry, or referenced only by role | "…among the many Loa including Ogou" |
   | 0.20  | Ambiguous — entity status uncertain; may be a place or abstract concept | "…the spirit of the mountain, unnamed" |
```

- [ ] **Step 2.2: Bump PROMPT_VERSION in extractor.py**

In `realms/ingestion/extractor.py`, change line:
```python
PROMPT_VERSION = "v4"
```
to:
```python
PROMPT_VERSION = "v5"
```

- [ ] **Step 2.3: Verify the prompt loads correctly**

```bash
cd /var/www/realms && docker compose exec -T realms-api python3 -c "
from realms.ingestion.extractor import PROMPT_VERSION
from pathlib import Path
prompt = Path('/app/realms/ingestion/prompts/extract_entities.md').read_text()
assert PROMPT_VERSION == 'v5'
assert 'Do NOT default to 0.9' in prompt
assert '| 0.95 |' in prompt
print('PROMPT_VERSION:', PROMPT_VERSION)
print('Calibration table present: OK')
" 2>/dev/null
```
Expected: `PROMPT_VERSION: v5` and `Calibration table present: OK`

- [ ] **Step 2.4: Commit**

```bash
cd /var/www/realms
git add realms/ingestion/prompts/extract_entities.md realms/ingestion/extractor.py
git commit -m "feat: update extraction prompt to v5 with confidence calibration table"
```

---

## Task 3: Normalizer Trigram Performance Fix

**Files:**
- Modify: `realms/ingestion/normalizer.py` (`_find_existing` function)
- Create: `tests/test_normalizer.py`

The trigram index `idx_entities_name_trgm` already exists (migration 0002). This task replaces the O(n) full-table Python loop with a `similarity()` query that uses it.

- [ ] **Step 3.1: Write the failing test**

```python
# tests/test_normalizer.py
"""Tests for entity normalizer, specifically dedup behavior."""
import pytest
from sqlalchemy import select
from realms.models import Entity, IngestionSource
from realms.ingestion.normalizer import _find_existing, upsert_entities
from realms.ingestion.extractor import ExtractedEntity

pytestmark = pytest.mark.integration


@pytest.fixture()
def source_id(db_session):
    s = IngestionSource(source_type="wikipedia", source_name="test",
                        url="https://example.com/test", ingestion_status="completed")
    db_session.add(s)
    db_session.flush()
    return s.id


def _make_entity(session, name, confidence=0.8, source_id=1):
    e = Entity(name=name, consensus_confidence=confidence,
               provenance_sources=[source_id], extraction_instances=[])
    session.add(e)
    session.flush()
    return e


def test_find_existing_exact_case_insensitive(db_session, source_id):
    _make_entity(db_session, "Tlaloc", source_id=source_id)
    result = _find_existing(db_session, "tlaloc")
    assert result is not None
    assert result.name == "Tlaloc"


def test_find_existing_trigram_fuzzy(db_session, source_id):
    """Should match despite diacritic or minor spelling difference."""
    _make_entity(db_session, "Tláloc", source_id=source_id)
    result = _find_existing(db_session, "Tlaloc")
    assert result is not None
    assert result.name == "Tláloc"


def test_find_existing_no_false_positive(db_session, source_id):
    """Should NOT match completely different names."""
    _make_entity(db_session, "Zeus", source_id=source_id)
    result = _find_existing(db_session, "Hera")
    assert result is None


def test_upsert_merges_duplicate(db_session, source_id):
    """upsert_entities should merge into existing entity, not create duplicate."""
    _make_entity(db_session, "Ogoun", source_id=source_id)

    extracted = ExtractedEntity(
        name="Ogou",  # alternate spelling
        entity_type="deity",
        alignment="ambiguous",
        realm="earth",
        description="Vodou spirit of iron and war.",
        powers=["combat"],
        domains=["iron"],
        cultural_associations=["Haitian Vodou"],
        geographical_associations=["Haiti"],
        alternate_names={},
        confidence=0.75,
        quote_context="Ogou is the warrior loa.",
        roles={},
    )
    result = upsert_entities(db_session, [extracted], source_id=source_id,
                             extraction_ids_by_name={"ogou": 999})

    all_entities = db_session.execute(select(Entity)).scalars().all()
    names = [e.name for e in all_entities]
    assert len([n for n in names if "ogou" in n.lower() or n.lower() == "ogoun"]) == 1
```

- [ ] **Step 3.2: Run tests to confirm they fail (or partially fail)**

```bash
cd /var/www/realms && docker compose exec -T realms-api pytest tests/test_normalizer.py -v 2>&1
```
Expected: `test_find_existing_trigram_fuzzy` fails (current code does full scan that may or may not catch it depending on stem matching) or tests error due to missing file.

- [ ] **Step 3.3: Replace `_find_existing` with trigram-backed implementation**

In `realms/ingestion/normalizer.py`, replace the `_find_existing` function (lines 44-61):

```python
def _find_existing(session: Session, name: str) -> Entity | None:
    """Find entity by exact name or trigram similarity (uses idx_entities_name_trgm)."""
    # 1. Exact case-insensitive
    hit = session.execute(
        select(Entity).where(Entity.name.ilike(name))
    ).scalar_one_or_none()
    if hit is not None:
        return hit

    # 2. Trigram similarity via pg_trgm — O(log n) using existing GIN index
    from sqlalchemy import func, text
    stem = _stem_key(name)
    rows = session.execute(
        select(Entity, func.similarity(Entity.name, name).label("sim"))
        .where(func.similarity(Entity.name, name) > 0.55)
        .order_by(func.similarity(Entity.name, name).desc())
        .limit(10)
    ).all()
    for row in rows:
        entity = row[0]
        sim = row[1]
        if _stem_key(entity.name) == stem or sim > 0.80:
            log.info("Trigram match: %r ~= existing %r (sim=%.2f)", name, entity.name, sim)
            return entity

    return None
```

- [ ] **Step 3.4: Run tests to confirm they pass**

```bash
cd /var/www/realms && docker compose exec -T realms-api pytest tests/test_normalizer.py -v 2>&1
```
Expected: All 4 tests PASS.

- [ ] **Step 3.5: Commit**

```bash
cd /var/www/realms
git add realms/ingestion/normalizer.py tests/test_normalizer.py
git commit -m "perf: replace O(n) entity dedup scan with pg_trgm similarity query"
```

---

## Task 4: Run Existing Dedup Script

The existing `scripts/dedupe_entities.py` already handles all 20 known duplicate pairs with a full audit trail.

- [ ] **Step 4.1: Dry-run dedup**

```bash
cd /var/www/realms && docker compose exec -T realms-api python -m scripts.dedupe_entities --dry-run 2>&1 | tail -30
```
Expected: Lists merge candidates for the 20 duplicate pairs (domovoi, genius, mania, etc.).

- [ ] **Step 4.2: Apply dedup**

```bash
cd /var/www/realms && docker compose exec -T realms-api python -m scripts.dedupe_entities --apply 2>&1
```
Expected: "Merged N pairs" with a log of each survivor/loser.

- [ ] **Step 4.3: Verify zero duplicates remain**

```bash
cd /var/www/realms && docker compose exec -T realms-api python3 -c "
import psycopg2, os
conn = psycopg2.connect(host=os.getenv('POSTGRES_HOST','localhost'), port=int(os.getenv('POSTGRES_PORT',5432)), user=os.getenv('POSTGRES_USER','realms'), password=os.getenv('POSTGRES_PASSWORD'), dbname=os.getenv('POSTGRES_DB','realms'))
cur = conn.cursor()
cur.execute(\"\"\"
    SELECT LOWER(TRIM(name)), COUNT(*) as dupes
    FROM entities WHERE review_status != 'merged'
    GROUP BY LOWER(TRIM(name)) HAVING COUNT(*) > 1
    ORDER BY dupes DESC LIMIT 10
\"\"\")
rows = cur.fetchall()
print('Remaining duplicates:', rows if rows else 'NONE')
conn.close()
" 2>/dev/null
```
Expected: `Remaining duplicates: NONE`

---

## Task 5: Zero-Extraction Rate Audit + Keyword Filter

- [ ] **Step 5.1: Count skipped-vs-empty sources from logs**

```bash
cd /var/www/realms && docker compose logs realms-ingestor --no-log-prefix 2>/dev/null | grep -c "skipped — no religion/mythology keywords" && echo "skipped by keyword filter" && docker compose logs realms-ingestor-2 --no-log-prefix 2>/dev/null | grep -c "skipped — no religion/mythology keywords" && echo "ingestor-2 skipped"
```

- [ ] **Step 5.2: Query actual zero-extraction completed sources**

```bash
cd /var/www/realms && docker compose exec -T realms-api python3 -c "
import psycopg2, os
conn = psycopg2.connect(host=os.getenv('POSTGRES_HOST','localhost'), port=int(os.getenv('POSTGRES_PORT',5432)), user=os.getenv('POSTGRES_USER','realms'), password=os.getenv('POSTGRES_PASSWORD'), dbname=os.getenv('POSTGRES_DB','realms'))
cur = conn.cursor()
cur.execute(\"\"\"
    SELECT source_type, COUNT(*) as zero
    FROM ingestion_sources s
    WHERE ingestion_status='completed'
    AND NOT EXISTS (SELECT 1 FROM ingested_entities ie WHERE ie.source_id = s.id)
    GROUP BY source_type ORDER BY zero DESC
\"\"\")
print('Zero-extraction completed sources by type:')
for r in cur.fetchall(): print(f'  {r[0]}: {r[1]}')
conn.close()
" 2>/dev/null
```

- [ ] **Step 5.3: Expand `_REL_KEYWORDS` if audit shows >30% were skipped by filter**

If the log count from Step 5.1 is >2,000 (i.e., the keyword filter is clearly over-aggressive), add these terms to `_REL_KEYWORDS` in `realms/ingestion/worker.py` after the existing set definition (around line 192):

```python
# Phenomenological encounter vocabulary — oral tradition and witness accounts
"apparition", "vision of", "folk belief", "folk spirit",
"traditional belief", "indigenous spirit", "ancestral being",
"reported encounter", "encountered by", "witnessed",
"seen by", "appeared to", "manifestation of",
"reported in folklore", "oral tradition", "oral account",
"spirit world", "spirit realm", "sacred being",
```

- [ ] **Step 5.4: Commit (if keywords were added)**

```bash
cd /var/www/realms
git add realms/ingestion/worker.py
git commit -m "feat: expand relevance filter with phenomenological encounter vocabulary"
```

---

## Task 6: Enable Integrity Gate on All Ingestors

**Files:**
- Modify: `docker-compose.yml` (environment blocks of all 4 ingestor services)

- [ ] **Step 6.1: Add env vars to all 4 ingestor environment blocks in docker-compose.yml**

For each of the four services (`realms-ingestor`, `realms-ingestor-2`, `realms-ingestor-3`, `realms-ingestor-4`), add to their `environment:` block:

```yaml
REALMS_INTEGRITY_GATE: "on"
REALMS_INTEGRITY_ACCEPT: "0.85"
REALMS_INTEGRITY_FLAG: "0.65"
```

- [ ] **Step 6.2: Restart ingestors to pick up new env**

```bash
cd /var/www/realms && docker compose up -d realms-ingestor realms-ingestor-2 realms-ingestor-3 realms-ingestor-4
```

- [ ] **Step 6.3: Verify gate is active**

```bash
cd /var/www/realms && docker compose exec -T realms-ingestor env | grep REALMS_INTEGRITY
```
Expected:
```
REALMS_INTEGRITY_GATE=on
REALMS_INTEGRITY_ACCEPT=0.85
REALMS_INTEGRITY_FLAG=0.65
```

- [ ] **Step 6.4: Commit**

```bash
cd /var/www/realms
git add docker-compose.yml
git commit -m "feat: enable integrity gate on all ingestor containers (accept=0.85, flag=0.65)"
```

---

## Task 7: Backfill Integrity + Brave Source Discovery

**Files:**
- Create: `scripts/backfill_integrity_and_sources.py`
- Create: `tests/test_backfill_integrity.py`

Processes the 1,770 entities with `consensus_confidence = 0.4`. For each:
1. Runs the integrity gate against stored extraction context
2. Flags the entity for review if gate score < 0.65
3. Searches Brave for Wikipedia/archive.org/edu URLs not already in `ingestion_sources`
4. Seeds new `pending` rows for the ingestors to pick up

- [ ] **Step 7.1: Write the failing tests**

```python
# tests/test_backfill_integrity.py
"""Unit tests for backfill_integrity_and_sources helpers."""
import pytest
from unittest.mock import patch, MagicMock
from scripts.backfill_integrity_and_sources import (
    search_brave_for_entity,
    infer_source_type,
    infer_credibility_score,
    filter_new_urls,
)


def test_infer_source_type_wikipedia():
    assert infer_source_type("https://en.wikipedia.org/wiki/Ogoun") == "wikipedia"


def test_infer_source_type_archive():
    assert infer_source_type("https://archive.org/details/some-book") == "archive_org"


def test_infer_source_type_edu():
    assert infer_source_type("https://www.harvard.edu/mythology/spirits") == "journal"


def test_infer_source_type_unknown():
    assert infer_source_type("https://randomsite.com/article") == "journal"


def test_infer_credibility_score():
    assert infer_credibility_score("wikipedia") == 0.80
    assert infer_credibility_score("archive_org") == 0.75
    assert infer_credibility_score("journal") == 0.70


def test_filter_new_urls_excludes_existing():
    existing = {"https://en.wikipedia.org/wiki/Ogoun"}
    urls = [
        "https://en.wikipedia.org/wiki/Ogoun",   # already exists
        "https://en.wikipedia.org/wiki/Shango",  # new
    ]
    result = filter_new_urls(urls, existing)
    assert result == ["https://en.wikipedia.org/wiki/Shango"]


def test_search_brave_returns_filtered_urls():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "web": {
            "results": [
                {"url": "https://en.wikipedia.org/wiki/Ogoun", "title": "Ogoun - Wikipedia"},
                {"url": "https://randomsite.com/not-relevant", "title": "Not useful"},
                {"url": "https://archive.org/details/yoruba-spirits", "title": "Yoruba Spirits"},
            ]
        }
    }
    with patch("scripts.backfill_integrity_and_sources.requests.get", return_value=mock_response):
        urls = search_brave_for_entity("Ogoun", "Yoruba", api_key="test-key")
    assert "https://en.wikipedia.org/wiki/Ogoun" in urls
    assert "https://archive.org/details/yoruba-spirits" in urls
    assert "https://randomsite.com/not-relevant" not in urls
```

- [ ] **Step 7.2: Run tests to confirm they fail**

```bash
cd /var/www/realms && docker compose exec -T realms-api pytest tests/test_backfill_integrity.py -v 2>&1 | head -20
```
Expected: `ImportError: cannot import name 'search_brave_for_entity'`

- [ ] **Step 7.3: Implement the backfill script**

```python
# scripts/backfill_integrity_and_sources.py
"""Integrity gate backfill + Brave source discovery for low-confidence entities.

Targets the ~1,770 entities with consensus_confidence = 0.4:
  1. Runs integrity gate against stored extraction_context
  2. Flags entity for human review if gate score < 0.65
  3. Searches Brave for Wikipedia/archive.org/edu sources not already in DB
  4. Seeds new pending ingestion_sources rows for the ingestors

Rate: 1 entity/second (Brave free tier: 2000 req/month).
Resumable: --offset N skips the first N entities.

Usage:
    docker exec realms-api python -m scripts.backfill_integrity_and_sources --dry-run
    docker exec realms-api python -m scripts.backfill_integrity_and_sources
    docker exec realms-api python -m scripts.backfill_integrity_and_sources --offset 500
"""
from __future__ import annotations

import argparse
import logging
import os
import time
from dataclasses import asdict

import requests
from sqlalchemy import select

from realms.ingestion.integrity_gate import run_gate
from realms.models import Entity, IngestedEntity, IngestionSource
from realms.utils.database import get_db_session

log = logging.getLogger("realms.backfill")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"

ALLOWED_DOMAINS = (
    "wikipedia.org",
    "archive.org",
    ".edu/",
    ".ac.uk/",
    ".edu.",
)


def infer_source_type(url: str) -> str:
    url_lower = url.lower()
    if "wikipedia.org" in url_lower:
        return "wikipedia"
    if "archive.org" in url_lower:
        return "archive_org"
    return "journal"


def infer_credibility_score(source_type: str) -> float:
    return {"wikipedia": 0.80, "archive_org": 0.75}.get(source_type, 0.70)


def filter_new_urls(urls: list[str], existing: set[str]) -> list[str]:
    """Return only URLs not already in ingestion_sources."""
    return [u for u in urls if u.strip().lower() not in existing]


def search_brave_for_entity(name: str, tradition: str | None, api_key: str) -> list[str]:
    """Search Brave for relevant sources. Returns list of filtered URLs."""
    if not api_key:
        log.warning("BRAVE_API_KEY not set — skipping Brave search")
        return []

    tradition_term = tradition or "mythology"
    query = f'"{name}" {tradition_term} mythology OR folklore OR spirit OR deity'
    try:
        resp = requests.get(
            BRAVE_URL,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
            params={"q": query, "count": 5},
            timeout=10,
        )
        if resp.status_code != 200:
            log.warning("Brave API returned %d for %r", resp.status_code, name)
            return []
        data = resp.json()
        results = data.get("web", {}).get("results", [])
        urls = []
        for r in results:
            url = r.get("url", "")
            if any(d in url.lower() for d in ALLOWED_DOMAINS):
                urls.append(url)
        return urls
    except Exception as exc:  # noqa: BLE001
        log.warning("Brave search failed for %r: %s", name, exc)
        return []


def _existing_urls(session) -> set[str]:
    rows = session.execute(select(IngestionSource.url).where(IngestionSource.url.isnot(None))).scalars().all()
    return {u.strip().lower() for u in rows if u}


def _run_integrity_for_entity(session, entity: Entity) -> float:
    """Run gate against all extraction_contexts for this entity. Returns best score."""
    if not entity.extraction_instances:
        return 0.0

    ie_rows = session.execute(
        select(IngestedEntity).where(IngestedEntity.id.in_(entity.extraction_instances))
    ).scalars().all()

    best_score = 0.0
    for ie in ie_rows:
        if not ie.extraction_context:
            continue
        raw = ie.raw_extracted_data if isinstance(ie.raw_extracted_data, dict) else {}
        if not raw:
            continue
        try:
            verdict = run_gate(raw, ie.extraction_context, accept_threshold=0.85, flag_threshold=0.65)
            if ie.integrity_meta is None:
                ie.integrity_meta = verdict.to_jsonb()
            if verdict.integrity_score > best_score:
                best_score = verdict.integrity_score
        except Exception as exc:  # noqa: BLE001
            log.warning("Gate error on entity %d: %s", entity.id, exc)
    return best_score


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()

    with get_db_session() as session:
        entities = session.execute(
            select(Entity)
            .where(Entity.consensus_confidence == 0.4)
            .order_by(Entity.id)
            .offset(args.offset)
        ).scalars().all()

    log.info("Processing %d low-confidence entities (offset=%d)", len(entities), args.offset)
    existing_urls = {}

    with get_db_session() as session:
        existing_urls = _existing_urls(session)

    flagged = 0
    sources_seeded = 0

    for i, entity in enumerate(entities):
        if (i + 1) % 50 == 0:
            log.info("Progress: %d/%d — flagged=%d sources_seeded=%d",
                     i + 1, len(entities), flagged, sources_seeded)

        with get_db_session() as session:
            ent = session.get(Entity, entity.id)
            if ent is None:
                continue

            # Step 1: integrity re-check
            best_score = _run_integrity_for_entity(session, ent)
            if best_score < 0.65 and ent.review_status not in ("approved", "merged"):
                ent.review_status = "flagged"
                flagged += 1
                log.info("[%d] %r flagged (gate_score=%.2f)", ent.id, ent.name, best_score)

            if not args.dry_run:
                session.commit()

        # Step 2: Brave source discovery
        tradition = None
        ca = entity.cultural_associations
        if isinstance(ca, list) and ca:
            tradition = str(ca[0])

        urls = search_brave_for_entity(entity.name, tradition, BRAVE_API_KEY)
        new_urls = filter_new_urls(urls, existing_urls)

        for url in new_urls:
            stype = infer_source_type(url)
            credibility = infer_credibility_score(stype)
            log.info("[%d] %r → new source: %s", entity.id, entity.name, url)
            if not args.dry_run:
                with get_db_session() as session:
                    row = IngestionSource(
                        source_type=stype,
                        source_name=f"{entity.name} (Brave discovery)",
                        url=url,
                        credibility_score=credibility,
                        ingestion_status="pending",
                    )
                    session.add(row)
                    session.commit()
                existing_urls.add(url.strip().lower())
                sources_seeded += 1

        time.sleep(1.0)  # 1 req/sec — Brave free tier

    log.info("Done. flagged=%d sources_seeded=%d", flagged, sources_seeded)


if __name__ == "__main__":
    main()
```

- [ ] **Step 7.4: Run unit tests to confirm they pass**

```bash
cd /var/www/realms && docker compose exec -T realms-api pytest tests/test_backfill_integrity.py -v 2>&1
```
Expected: All 6 tests PASS.

- [ ] **Step 7.5: Verify BRAVE_API_KEY is set**

```bash
cd /var/www/realms && docker compose exec -T realms-api env | grep BRAVE
```
Expected: `BRAVE_API_KEY=BSA...`  
If missing: add `BRAVE_API_KEY=<your-key>` to `.env`, then `docker compose up -d realms-api`.

- [ ] **Step 7.6: Dry-run the backfill**

```bash
cd /var/www/realms && docker compose exec -T realms-api python -m scripts.backfill_integrity_and_sources --dry-run 2>&1 | head -40
```
Expected: Logs entities being checked, Brave URLs found, flagged count. No DB writes.

- [ ] **Step 7.7: Run the full backfill in background (~30 min)**

```bash
cd /var/www/realms && docker compose exec -d realms-api python -m scripts.backfill_integrity_and_sources
```

Monitor progress:
```bash
cd /var/www/realms && docker compose exec -T realms-api tail -f /proc/1/fd/1 2>/dev/null | grep backfill
```
Expected: Progress logs every 50 entities; final "Done. flagged=N sources_seeded=N"

- [ ] **Step 7.8: Verify results**

```bash
cd /var/www/realms && docker compose exec -T realms-api python3 -c "
import psycopg2, os
conn = psycopg2.connect(host=os.getenv('POSTGRES_HOST','localhost'), port=int(os.getenv('POSTGRES_PORT',5432)), user=os.getenv('POSTGRES_USER','realms'), password=os.getenv('POSTGRES_PASSWORD'), dbname=os.getenv('POSTGRES_DB','realms'))
cur = conn.cursor()
cur.execute(\"SELECT COUNT(*) FROM entities WHERE consensus_confidence=0.4 AND integrity_meta IS NOT NULL\", )
print('Low-conf entities with gate results:', cur.fetchone()[0])
cur.execute(\"SELECT COUNT(*) FROM entities WHERE review_status='flagged'\")
print('Flagged for review:', cur.fetchone()[0])
cur.execute(\"SELECT COUNT(*) FROM ingestion_sources WHERE source_name LIKE '%Brave discovery%' AND ingestion_status='pending'\")
print('New Brave-seeded sources pending:', cur.fetchone()[0])
conn.close()
" 2>/dev/null
```
Expected:
- `Low-conf entities with gate results:` ≥ 1,000
- `Flagged for review:` > 0
- `New Brave-seeded sources pending:` ≥ 200

- [ ] **Step 7.9: Commit**

```bash
cd /var/www/realms
git add scripts/backfill_integrity_and_sources.py tests/test_backfill_integrity.py
git commit -m "feat: backfill integrity gate + Brave source discovery for low-confidence entities"
```

---

## Final Verification

- [ ] **Run full test suite**

```bash
cd /var/www/realms && docker compose exec -T realms-api pytest tests/ -v --ignore=tests/test_fetchers.py 2>&1 | tail -20
```
Expected: All tests pass (fetchers excluded — they hit live HTTP).

- [ ] **Confirm success criteria**

```bash
cd /var/www/realms && docker compose exec -T realms-api python3 -c "
import psycopg2, os
conn = psycopg2.connect(host=os.getenv('POSTGRES_HOST','localhost'), port=int(os.getenv('POSTGRES_PORT',5432)), user=os.getenv('POSTGRES_USER','realms'), password=os.getenv('POSTGRES_PASSWORD'), dbname=os.getenv('POSTGRES_DB','realms'))
cur = conn.cursor()
cur.execute(\"SELECT COUNT(*) FROM entities WHERE description ILIKE '%marvel%' OR description ILIKE '%fictional character%'\")
print('Fictional entities remaining:', cur.fetchone()[0], '(want 0)')
cur.execute(\"SELECT STDDEV(consensus_confidence), PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY consensus_confidence) FROM entities WHERE consensus_confidence IS NOT NULL\")
r = cur.fetchone()
print(f'Confidence std={r[0]:.3f} (want >0.10), p50={r[1]:.3f} (want !=0.9)')
cur.execute(\"SELECT COUNT(*) FROM entities WHERE review_status='merged'\")
print('Merged duplicates:', cur.fetchone()[0], '(want >=20)')
conn.close()
" 2>/dev/null
```
