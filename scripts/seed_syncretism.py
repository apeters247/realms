"""Hand-curated syncretism + equivalence edges between entities.

Fills the obvious cross-tradition links the LLM extractor keeps missing:

  - Greek ↔ Roman pantheon mappings  (Zeus↔Jupiter, Ares↔Mars, …)
  - Catholic saints ↔ Yoruba orishas (Our Lady of Charity↔Oshun, …)
  - Norse ↔ Germanic  (Odin↔Wotan, Thor↔Donar)
  - Egyptian ↔ Greek syncretism (Thoth↔Hermes Trismegistus, Isis↔Aphrodite-Urania)

Each pair writes a symmetric ``syncretized_with`` edge with source=curated,
strength=strong, confidence=0.95.

Idempotent — safe to re-run. Skips pairs where an edge already exists.

Usage:
  docker exec realms-api python -m scripts.seed_syncretism --dry-run
  docker exec realms-api python -m scripts.seed_syncretism --apply
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import unicodedata
from typing import Iterable

from sqlalchemy import and_, or_, select, text

from realms.models import Entity, EntityRelationship, ReviewAction
from realms.utils.database import get_db_session

log = logging.getLogger("realms.seed_syncretism")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _norm(s: str) -> str:
    nfd = unicodedata.normalize("NFD", s or "")
    no_dia = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", no_dia.lower().strip())


# ─── PAIR LISTS ─────────────────────────────────────────────────────────

# Each entry is (name_a, name_b, [optional cultures_a], [optional cultures_b], note)
# We try exact name match against the DB; alternate_names are also searched.

GREEK_ROMAN: list[tuple[str, str, str]] = [
    ("Zeus", "Jupiter", "king of gods"),
    ("Hera", "Juno", "queen of gods, marriage"),
    ("Poseidon", "Neptune", "sea"),
    ("Demeter", "Ceres", "harvest, fertility"),
    ("Apollo", "Apollo", "same in both Roman + Greek; kept for symmetry"),
    ("Artemis", "Diana", "moon, hunt"),
    ("Ares", "Mars", "war"),
    ("Aphrodite", "Venus", "love"),
    ("Hephaestus", "Vulcan", "forge"),
    ("Hermes", "Mercury", "messenger, trade"),
    ("Athena", "Minerva", "wisdom, war"),
    ("Dionysus", "Bacchus", "wine"),
    ("Hestia", "Vesta", "hearth"),
    ("Hades", "Pluto", "underworld"),
    ("Persephone", "Proserpina", "underworld queen"),
    ("Cronus", "Saturn", "time, titan"),
    ("Rhea", "Ops", "earth mother"),
    ("Uranus", "Caelus", "sky"),
    ("Gaia", "Terra", "earth"),
    ("Helios", "Sol", "sun"),
    ("Selene", "Luna", "moon"),
    ("Eos", "Aurora", "dawn"),
    ("Eros", "Cupid", "desire"),
    ("Nike", "Victoria", "victory"),
    ("Tyche", "Fortuna", "fortune"),
    ("Nemesis", "Invidia", "vengeance (loose)"),
    ("Hecate", "Trivia", "crossroads, magic"),
    ("Asclepius", "Aesculapius", "healing"),
    ("Heracles", "Hercules", "hero / apotheosis"),
    ("Pan", "Faunus", "wilderness (partial)"),
    ("Thanatos", "Mors", "death personification"),
    ("Hypnos", "Somnus", "sleep"),
    ("Nyx", "Nox", "night"),
    ("Hebe", "Juventas", "youth"),
    ("Iris", "Arcus", "rainbow (partial)"),
    ("Pluto", "Dis Pater", "underworld wealth"),
    ("Pan", "Silvanus", "forest (partial)"),
]

# Yoruba orisha ↔ Catholic saint syncretism as practiced in Cuban Santería,
# Brazilian Candomblé, and Haitian Vodou. Sources: Murphy (2001), Murphy
# (1988), Bascom (1969). These are the widely-attested canonical pairings;
# regional variants exist but these are the dominant mappings.
ORISHA_SAINT: list[tuple[str, str, str]] = [
    ("Yemoja", "Our Lady of Regla", "Santería / Yoruba sea mother"),
    ("Oshun", "Our Lady of Charity", "Santería — Cuba national patroness"),
    ("Shango", "Saint Barbara", "thunder, fire"),
    ("Obatala", "Our Lady of Mercy", "purity, creation, Santería"),
    ("Oya", "Saint Theresa", "winds, storms, cemetery (Santería)"),
    ("Elegua", "Saint Anthony of Padua", "crossroads, openings"),
    ("Eshu", "Saint Anthony of Padua", "trickster"),
    ("Oggun", "Saint Peter", "iron, war"),
    ("Ogun", "Saint Peter", "iron, war (spelling variant)"),
    ("Ochosi", "Saint Norbert", "hunt"),
    ("Babalu-Aye", "Saint Lazarus", "disease, healing"),
    ("Babalu Aye", "Saint Lazarus", "disease, healing (spelling variant)"),
    ("Orunmila", "Saint Francis of Assisi", "wisdom, divination (Santería)"),
    ("Orula", "Saint Francis of Assisi", "Ifá, wisdom"),
    ("Ibeji", "Saints Cosmas and Damian", "twin saints"),
    ("Nana Buruku", "Saint Anne", "grandmother goddess"),
]

EGYPTIAN_HELLENIC: list[tuple[str, str, str]] = [
    ("Thoth", "Hermes", "writing, magic → Hermes Trismegistus synthesis"),
    ("Anubis", "Hermanubis", "Greco-Roman psychopomp syncretism"),
    ("Isis", "Demeter", "mother, mysteries, Greco-Roman mystery cult"),
    ("Isis", "Aphrodite", "partial syncretism in Greco-Roman period"),
    ("Osiris", "Serapis", "Hellenistic Egyptian syncretism"),
    ("Ptah", "Hephaestus", "craftsman, maker"),
    ("Ra", "Helios", "sun"),
    ("Horus", "Apollo", "son of chief god, sun aspects"),
    ("Set", "Typhon", "chaos"),
    ("Hathor", "Aphrodite", "love, music"),
    ("Bastet", "Artemis", "feline, protection"),
    ("Neith", "Athena", "weaving, war, wisdom"),
    ("Khnum", "Hephaestus", "craftsman, shaper"),
    ("Min", "Pan", "fertility"),
    ("Amun", "Zeus", "king of gods (Zeus-Ammon)"),
    ("Apis", "Dionysus", "bull cult syncretism"),
]

NORSE_GERMANIC: list[tuple[str, str, str]] = [
    ("Odin", "Wodan", "Germanic form"),
    ("Odin", "Woden", "Anglo-Saxon form"),
    ("Odin", "Wotan", "modern Germanic reconstruction"),
    ("Thor", "Donar", "Germanic thunder"),
    ("Thor", "Thunor", "Anglo-Saxon thunder"),
    ("Tyr", "Tiwaz", "Proto-Germanic war god"),
    ("Tyr", "Tiw", "Anglo-Saxon"),
    ("Freya", "Freyja", "same entity; spelling"),
    ("Freyr", "Frey", "same entity; spelling"),
    ("Frigg", "Frige", "Anglo-Saxon form"),
    ("Loki", "Loki", "same entity — kept for symmetry"),
    ("Baldr", "Baldur", "spelling variant"),
    ("Nerthus", "Njörðr", "Proto-Germanic earth ↔ Norse sea (related etymology)"),
]

MESOPOTAMIAN_LINKS: list[tuple[str, str, str]] = [
    ("Inanna", "Ishtar", "Sumerian → Akkadian"),
    ("Inanna", "Astarte", "Canaanite successor"),
    ("Ishtar", "Astarte", "Akkadian → Canaanite"),
    ("Astarte", "Aphrodite", "Canaanite → Greek"),
    ("Enki", "Ea", "Sumerian → Akkadian water god"),
    ("Enlil", "Ellil", "Sumerian → Akkadian storm"),
    ("Utu", "Shamash", "Sumerian → Akkadian sun"),
    ("Nanna", "Sin", "Sumerian → Akkadian moon"),
    ("Baal", "Hadad", "Canaanite → Semitic storm"),
    ("Adonis", "Tammuz", "Greek → Mesopotamian dying god"),
    ("Tammuz", "Dumuzid", "Akkadian → Sumerian"),
]

# Hindu ↔ Buddhist mappings (deva absorbed into Buddhist cosmology)
HINDU_BUDDHIST: list[tuple[str, str, str]] = [
    ("Indra", "Sakra", "king of devas, absorbed into Buddhism"),
    ("Brahma", "Brahmā", "creator, absorbed into Buddhism"),
    ("Yama", "Yama (Buddhism)", "king of death"),
    ("Ganesha", "Vinayaka", "same entity; names"),
    ("Saraswati", "Benzaiten", "Japanese Buddhist syncretism"),
    ("Lakshmi", "Kichijoten", "Japanese Buddhist syncretism"),
    ("Mahakala", "Daikokuten", "Japanese Buddhist syncretism"),
]


ALL_PAIRS: list[tuple[str, list[tuple[str, str, str]]]] = [
    ("greek_roman", GREEK_ROMAN),
    ("orisha_saint", ORISHA_SAINT),
    ("egyptian_hellenic", EGYPTIAN_HELLENIC),
    ("norse_germanic", NORSE_GERMANIC),
    ("mesopotamian_lineage", MESOPOTAMIAN_LINKS),
    ("hindu_buddhist", HINDU_BUDDHIST),
]


# ─── matcher ────────────────────────────────────────────────────────────

def _find_entity(session, name: str) -> Entity | None:
    """Find by exact name first, then by alternate_names JSONB, then ILIKE."""
    n = _norm(name)
    # Exact (case-insensitive) match on name
    e = session.execute(
        select(Entity).where(Entity.review_status != "merged")
        .where(Entity.name.ilike(name))
    ).scalars().first()
    if e:
        return e
    # Alt-names (JSONB) — textual search via the ::text cast
    e = session.execute(
        select(Entity).where(Entity.review_status != "merged")
        .where(text("alternate_names::text ILIKE :pat").bindparams(pat=f"%{name}%"))
    ).scalars().first()
    if e and _norm(name) in [_norm(a) for vs in (e.alternate_names or {}).values() for a in (vs or [])]:
        return e
    # Fuzzy: any entity whose normalised name matches.
    rows = session.execute(
        select(Entity).where(Entity.review_status != "merged")
        .where(Entity.name.ilike(f"%{name}%"))
        .limit(10)
    ).scalars().all()
    for r in rows:
        if _norm(r.name) == n:
            return r
    return None


def seed(apply: bool) -> dict:
    added = 0
    skipped_existing = 0
    unresolved: list[str] = []
    by_bucket: dict[str, dict] = {}

    with get_db_session() as session:
        for bucket_name, pairs in ALL_PAIRS:
            bucket_added = 0
            bucket_unresolved = []
            bucket_existing = 0
            for a_name, b_name, note in pairs:
                a = _find_entity(session, a_name)
                b = _find_entity(session, b_name)
                if a is None or b is None:
                    bucket_unresolved.append(
                        f"{a_name}→{'OK' if a else '??'}, {b_name}→{'OK' if b else '??'}"
                    )
                    continue
                if a.id == b.id:
                    continue  # same entity — skip (rare but possible)

                # Skip if a syncretized_with edge already exists either direction.
                exists = session.execute(
                    select(EntityRelationship).where(
                        EntityRelationship.relationship_type == "syncretized_with",
                        or_(
                            and_(
                                EntityRelationship.source_entity_id == a.id,
                                EntityRelationship.target_entity_id == b.id,
                            ),
                            and_(
                                EntityRelationship.source_entity_id == b.id,
                                EntityRelationship.target_entity_id == a.id,
                            ),
                        ),
                    )
                ).scalars().first()
                if exists:
                    bucket_existing += 1
                    continue

                if apply:
                    # Symmetric: write both directions so either endpoint
                    # surfaces the link in "out relationships".
                    for src, tgt in ((a, b), (b, a)):
                        session.add(EntityRelationship(
                            source_entity_id=src.id,
                            target_entity_id=tgt.id,
                            relationship_type="syncretized_with",
                            description=f"curated:{bucket_name}: {note}",
                            strength="strong",
                            extraction_confidence=0.95,
                            historical_period=None,
                        ))
                    session.add(ReviewAction(
                        entity_id=a.id,
                        reviewer="syncretism-seeder",
                        action="syncretism_link",
                        field=None,
                        old_value=None,
                        new_value={
                            "other_entity_id": b.id,
                            "other_entity_name": b.name,
                            "bucket": bucket_name,
                            "note": note,
                        },
                        note=f"curated syncretism pair: {a.name} ↔ {b.name}",
                    ))
                bucket_added += 1
            if apply:
                session.commit()
            added += bucket_added
            skipped_existing += bucket_existing
            unresolved.extend(bucket_unresolved)
            by_bucket[bucket_name] = {
                "added": bucket_added,
                "existing": bucket_existing,
                "unresolved": len(bucket_unresolved),
            }
            log.info("%-22s  added=%3d  existing=%3d  unresolved=%3d",
                     bucket_name, bucket_added, bucket_existing, len(bucket_unresolved))

    return {
        "added_pairs": added,
        "edges_written": added * 2 if apply else 0,
        "existing": skipped_existing,
        "unresolved": unresolved[:30],  # truncate
        "n_unresolved": len(unresolved),
        "per_bucket": by_bucket,
        "dry_run": not apply,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()
    summary = seed(apply=args.apply)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
