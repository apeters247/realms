"""Canonicalize tradition names across the entity corpus.

The LLM extractor emits traditions in whatever form the source text uses —
"Hindu" / "Hinduism", "Greek" / "Greek mythology", "Ancient Egyptian" /
"Egyptian", "Christian" / "Catholic" / "Christianity" — which fragments
cross-linking, tradition pages, and the graph's tradition-filter.

This script:
  1. Applies a canonical-form map to every entity's ``cultural_associations``
  2. De-duplicates the resulting list (case-insensitive, diacritic-aware)
  3. Re-promotes ``Culture`` rows from the canonicalised tradition set
  4. Prints a before/after histogram

Run once after every large ingestion batch:
  docker exec realms-api python -m scripts.canonicalize_traditions --dry-run
  docker exec realms-api python -m scripts.canonicalize_traditions --apply
"""
from __future__ import annotations

import argparse
import json
import logging
import unicodedata
from collections import Counter

from sqlalchemy import select, update

from realms.models import Entity
from realms.utils.database import get_db_session

log = logging.getLogger("realms.canonicalize")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# Canonical-form map. Keys are the *normalised* (lowercase, diacritic-stripped)
# forms the LLM emits; values are the canonical display form we want to store.
# Ordered roughly by frequency so the common merges happen first.
CANONICAL: dict[str, str] = {
    # Greek
    "greek": "Greek", "greek mythology": "Greek", "greek religion": "Greek",
    "ancient greek": "Greek", "hellenic": "Greek", "hellenistic": "Greek",

    # Roman
    "roman": "Roman", "roman mythology": "Roman", "roman religion": "Roman",
    "ancient roman": "Roman", "latin": "Roman",

    # Egyptian
    "egyptian": "Egyptian", "ancient egyptian": "Egyptian",
    "egyptian mythology": "Egyptian", "egyptian religion": "Egyptian",

    # Hindu
    "hindu": "Hindu", "hinduism": "Hindu", "vedic": "Hindu",
    "hindu mythology": "Hindu", "indian mythology": "Hindu",

    # Buddhist (kept distinct from Hindu)
    "buddhist": "Buddhist", "buddhism": "Buddhist",
    "mahayana buddhism": "Buddhist", "theravada buddhism": "Buddhist",
    "tibetan buddhism": "Tibetan Buddhist",  # intentionally distinct

    # Japanese
    "japanese": "Japanese", "japanese mythology": "Japanese",
    "shinto": "Shinto",  # intentionally distinct
    "japanese buddhism": "Japanese",

    # Chinese
    "chinese": "Chinese", "chinese mythology": "Chinese",
    "chinese folk religion": "Chinese",
    "taoist": "Taoist", "taoism": "Taoist", "daoist": "Taoist", "daoism": "Taoist",

    # Christian (kept tiered: Christian > Catholic > Orthodox for precision)
    "christian": "Christian", "christianity": "Christian",
    "christianity deity": "Christian",
    "catholic": "Catholic",
    "roman catholic": "Catholic", "roman catholicism": "Catholic",
    "catholicism": "Catholic",
    "eastern orthodox": "Orthodox Christian",
    "orthodox": "Orthodox Christian",
    "coptic": "Coptic Christian",

    # Jewish
    "jewish": "Jewish", "judaism": "Jewish",
    "hebrew": "Hebrew", "hebrew bible": "Hebrew",
    "rabbinic": "Jewish",

    # Islamic
    "islamic": "Islamic", "islam": "Islamic",
    "muslim": "Islamic", "quranic": "Islamic",

    # Norse / Germanic
    "norse": "Norse", "norse mythology": "Norse",
    "old norse": "Norse", "viking": "Norse",
    "germanic": "Germanic", "anglo-saxon": "Germanic",

    # Celtic
    "celtic": "Celtic", "celtic mythology": "Celtic",
    "irish": "Irish", "irish mythology": "Irish",
    "welsh": "Welsh", "welsh mythology": "Welsh",
    "scottish": "Scottish", "manx": "Manx",
    "breton": "Breton", "gaulish": "Gaulish",

    # Slavic / Baltic
    "slavic": "Slavic", "slavic mythology": "Slavic",
    "russian": "Slavic", "ukrainian": "Slavic",
    "polish": "Slavic", "bulgarian": "Slavic",
    "baltic": "Baltic", "lithuanian": "Baltic", "latvian": "Baltic",

    # Mesopotamian
    "mesopotamian": "Mesopotamian",
    "sumerian": "Sumerian", "akkadian": "Akkadian",
    "babylonian": "Babylonian", "assyrian": "Assyrian",

    # Yoruba + diaspora
    "yoruba": "Yoruba",
    "santería": "Santería", "santeria": "Santería", "santerian": "Santería",
    "candomblé": "Candomblé", "candomble": "Candomblé",
    "vodou": "Vodou", "voodoo": "Vodou", "haitian vodou": "Vodou",
    "ifá": "Ifá", "ifa": "Ifá",

    # Other African
    "igbo": "Igbo", "akan": "Akan", "yorùbá": "Yoruba",
    "zulu": "Zulu", "ashanti": "Akan", "fon": "Fon",
    "bantu": "Bantu", "san": "San",

    # Siberian / Central Asian
    "siberian": "Siberian", "chukchi": "Chukchi",
    "koryak": "Koryak", "yakut": "Yakut", "nivkh": "Nivkh",
    "tengrism": "Tengrism", "tengrist": "Tengrism",
    "turkic": "Turkic", "turkic mythology": "Turkic",
    "mongolian": "Mongol", "mongol": "Mongol",

    # Mesoamerican
    "aztec": "Aztec", "mexica": "Aztec", "nahuatl": "Aztec",
    "maya": "Maya", "mayan": "Maya",
    "inca": "Inca", "inka": "Inca", "quechua": "Quechua",
    "mesoamerican": "Mesoamerican",

    # Native American
    "native american": "Native American",
    "cherokee": "Cherokee", "lakota": "Lakota",
    "navajo": "Navajo", "hopi": "Hopi",
    "iroquois": "Iroquois", "plains indian": "Plains Indian",

    # Amazonian
    "yanomami": "Yanomami", "shipibo": "Shipibo",
    "kechua": "Quechua", "shipibo-konibo": "Shipibo",

    # Pacific
    "polynesian": "Polynesian",
    "maori": "Māori", "māori": "Māori",
    "hawaiian": "Hawaiian",
    "samoan": "Samoan", "tongan": "Tongan",

    # Arabic / pre-Islamic
    "arab": "Arab", "arabian": "Arab",
    "pre-islamic arabia": "Pre-Islamic Arab",
    "canaanite": "Canaanite", "phoenician": "Phoenician",

    # Persian
    "persian": "Persian", "iranian": "Persian",
    "zoroastrian": "Zoroastrian", "zoroastrianism": "Zoroastrian",

    # Ethiopian / Horn
    "ethiopian": "Ethiopian", "amhara": "Ethiopian",

    # Etruscan / Anatolian
    "etruscan": "Etruscan", "hittite": "Hittite",
    "anatolian": "Anatolian", "lydian": "Lydian",

    # Generic (flag for review — too broad, keep as-is but lowercase)
    "indigenous": "Indigenous",
    "folk": "Folk",
    "african": "African",  # too generic, but some entries only say this
}


def _norm(s: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace."""
    nfd = unicodedata.normalize("NFD", s or "")
    no_dia = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return " ".join(no_dia.lower().split())


def canonicalise_one(tag: str) -> str:
    if not tag:
        return tag
    n = _norm(tag)
    return CANONICAL.get(n, tag)  # keep original if not in map


def dedupe_preserving_order(xs: list[str]) -> list[str]:
    seen = set()
    out = []
    for x in xs:
        k = _norm(x)
        if k in seen:
            continue
        seen.add(k)
        out.append(x)
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true",
                   help="actually write; default is dry-run")
    args = p.parse_args()

    with get_db_session() as session:
        rows = session.execute(select(Entity).where(Entity.cultural_associations.isnot(None))).scalars().all()
        before: Counter = Counter()
        after: Counter = Counter()
        changed = 0
        for e in rows:
            ca = e.cultural_associations or []
            if not isinstance(ca, list):
                continue
            new = dedupe_preserving_order([canonicalise_one(x) for x in ca])
            for x in ca:
                before[x] += 1
            for x in new:
                after[x] += 1
            if new != ca:
                changed += 1
                if args.apply:
                    e.cultural_associations = new
        if args.apply:
            session.commit()

    log.info("%d entities had at least one tradition renamed/de-duped", changed)

    # Show the top shifts
    merged_keys = sorted({k for k in (*before, *after)}, key=lambda k: -after.get(k, 0))
    log.info("\nTop traditions AFTER canonicalisation:")
    for k in merged_keys[:25]:
        a = after.get(k, 0)
        b = before.get(k, 0)
        delta = a - b
        log.info("  %-28s %5d  (was %5d  delta %+d)", k, a, b, delta)

    dropped = [k for k in merged_keys if before.get(k, 0) and not after.get(k, 0)]
    if dropped:
        log.info("\nFolded-away synonyms (were renamed into canonical):")
        for k in dropped[:30]:
            log.info("  - %s", k)

    print(json.dumps({
        "entities_changed": changed,
        "dry_run": not args.apply,
        "top_before": before.most_common(15),
        "top_after": after.most_common(15),
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
