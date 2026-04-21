"""Seed IngestionSource rows pointing at classical primary-source pages.

Two sources, both public-domain and scholarly:
  - **Theoi.com** — curated excerpts from Greek/Roman primary sources
    (Homer, Hesiod, Apollodorus, Pausanias, Ovid, …), organised by entity.
  - **Perseus Digital Library** — hosts the canonical Greek & Latin texts
    with English translation, indexed by entity.

We limit the seed list to a hand-curated set of ~220 Greek + Roman + Egyptian
entity pages. No BFS over the full site — the aim is a high-quality
primary-source overlay, not to re-ingest every cult statue.

Usage:
  docker exec realms-api python -m scripts.seed_classical_primary --dry-run
  docker exec realms-api python -m scripts.seed_classical_primary
"""
from __future__ import annotations

import argparse
import json
import logging

from sqlalchemy import select

from realms.models import IngestionSource
from realms.utils.database import get_db_session

log = logging.getLogger("realms.seed_classical")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# Theoi.com organises each entity under /<Category>/<Name>.html paths.
# This seed list covers the major deities, Titans, nymphs, heroes, and
# the Orphic / Mystery-cult figures.
THEOI: list[tuple[str, str]] = [
    # Olympians
    ("Zeus", "https://www.theoi.com/Olympios/Zeus.html"),
    ("Hera", "https://www.theoi.com/Olympios/Hera.html"),
    ("Poseidon", "https://www.theoi.com/Olympios/Poseidon.html"),
    ("Demeter", "https://www.theoi.com/Olympios/Demeter.html"),
    ("Apollo", "https://www.theoi.com/Olympios/Apollon.html"),
    ("Artemis", "https://www.theoi.com/Olympios/Artemis.html"),
    ("Ares", "https://www.theoi.com/Olympios/Ares.html"),
    ("Aphrodite", "https://www.theoi.com/Olympios/Aphrodite.html"),
    ("Hephaestus", "https://www.theoi.com/Olympios/Hephaistos.html"),
    ("Hermes", "https://www.theoi.com/Olympios/Hermes.html"),
    ("Athena", "https://www.theoi.com/Olympios/Athena.html"),
    ("Dionysus", "https://www.theoi.com/Olympios/Dionysos.html"),
    ("Hestia", "https://www.theoi.com/Olympios/Hestia.html"),

    # Titans
    ("Cronus", "https://www.theoi.com/Titan/TitanKronos.html"),
    ("Rhea", "https://www.theoi.com/Titan/TitanisRhea.html"),
    ("Hyperion", "https://www.theoi.com/Titan/TitanHyperion.html"),
    ("Theia", "https://www.theoi.com/Titan/TitanisTheia.html"),
    ("Iapetus", "https://www.theoi.com/Titan/TitanIapetos.html"),
    ("Themis", "https://www.theoi.com/Titan/TitanisThemis.html"),
    ("Prometheus", "https://www.theoi.com/Titan/TitanPrometheus.html"),
    ("Atlas", "https://www.theoi.com/Titan/TitanAtlas.html"),
    ("Helios", "https://www.theoi.com/Titan/Helios.html"),
    ("Selene", "https://www.theoi.com/Titan/Selene.html"),
    ("Eos", "https://www.theoi.com/Titan/Eos.html"),

    # Underworld
    ("Hades", "https://www.theoi.com/Khthonios/Haides.html"),
    ("Persephone", "https://www.theoi.com/Khthonios/Persephone.html"),
    ("Hecate", "https://www.theoi.com/Khthonios/Hekate.html"),
    ("Thanatos", "https://www.theoi.com/Daimon/Thanatos.html"),
    ("Hypnos", "https://www.theoi.com/Daimon/Hypnos.html"),
    ("Charon", "https://www.theoi.com/Khthonios/Kharon.html"),
    ("Cerberus", "https://www.theoi.com/Ther/KuonKerberos.html"),

    # Primordials
    ("Chaos", "https://www.theoi.com/Protogenos/Khaos.html"),
    ("Gaia", "https://www.theoi.com/Protogenos/Gaia.html"),
    ("Uranus", "https://www.theoi.com/Protogenos/Ouranos.html"),
    ("Nyx", "https://www.theoi.com/Protogenos/Nyx.html"),
    ("Erebus", "https://www.theoi.com/Protogenos/Erebos.html"),
    ("Tartarus", "https://www.theoi.com/Protogenos/Tartaros.html"),
    ("Eros", "https://www.theoi.com/Protogenos/Eros.html"),
    ("Pontus", "https://www.theoi.com/Protogenos/Pontos.html"),

    # Nymphs and nature spirits
    ("Naiads", "https://www.theoi.com/Nymphe/Naiades.html"),
    ("Dryads", "https://www.theoi.com/Nymphe/Dryades.html"),
    ("Oreads", "https://www.theoi.com/Nymphe/Oreades.html"),
    ("Nereids", "https://www.theoi.com/Nymphe/Nereides.html"),
    ("Muses", "https://www.theoi.com/Ouranios/Mousai.html"),
    ("Graces", "https://www.theoi.com/Ouranios/Kharites.html"),
    ("Horae", "https://www.theoi.com/Ouranios/Horai.html"),
    ("Moirai", "https://www.theoi.com/Daimon/Moirai.html"),
    ("Erinyes", "https://www.theoi.com/Khthonios/Erinyes.html"),

    # Heroes / demigods
    ("Heracles", "https://www.theoi.com/Heros/Herakles.html"),
    ("Perseus", "https://www.theoi.com/Heros/Perseus.html"),
    ("Theseus", "https://www.theoi.com/Heros/Theseus.html"),
    ("Bellerophon", "https://www.theoi.com/Heros/Bellerophontes.html"),
    ("Orpheus", "https://www.theoi.com/Heros/Orpheus.html"),
    ("Achilles", "https://www.theoi.com/Heros/Akhilleus.html"),

    # Monsters
    ("Typhon", "https://www.theoi.com/Georgikos/DrakonTyphon.html"),
    ("Echidna", "https://www.theoi.com/Ther/DrakainaEkhidna.html"),
    ("Medusa", "https://www.theoi.com/Pontios/Medousa.html"),
    ("Minotaur", "https://www.theoi.com/Ther/Minotauros.html"),
    ("Chimera", "https://www.theoi.com/Ther/Khimaira.html"),
    ("Hydra", "https://www.theoi.com/Ther/DrakonHydraLernaia.html"),
    ("Sphinx", "https://www.theoi.com/Ther/Sphinx.html"),

    # Minor gods worth linking for relationships
    ("Pan", "https://www.theoi.com/Georgikos/Pan.html"),
    ("Priapus", "https://www.theoi.com/Georgikos/Priapos.html"),
    ("Asclepius", "https://www.theoi.com/Ouranios/Asklepios.html"),
    ("Nike", "https://www.theoi.com/Daimon/Nike.html"),
    ("Iris", "https://www.theoi.com/Pontios/Iris.html"),
    ("Nemesis", "https://www.theoi.com/Daimon/Nemesis.html"),
    ("Tyche", "https://www.theoi.com/Daimon/Tykhe.html"),
]


# Perseus collection pages we want to re-ingest as secondary source material.
# Perseus texts are English translations that include primary citations.
PERSEUS: list[tuple[str, str]] = [
    ("Homeric Hymns",
     "http://www.perseus.tufts.edu/hopper/text?doc=Perseus:text:1999.01.0138"),
    ("Hesiod, Theogony",
     "http://www.perseus.tufts.edu/hopper/text?doc=Perseus:text:1999.01.0130"),
    ("Apollodorus, Library",
     "http://www.perseus.tufts.edu/hopper/text?doc=Perseus:text:1999.01.0022"),
    ("Pausanias, Description of Greece",
     "http://www.perseus.tufts.edu/hopper/text?doc=Perseus:text:1999.01.0160"),
    ("Ovid, Metamorphoses (English)",
     "http://www.perseus.tufts.edu/hopper/text?doc=Perseus%3Atext%3A1999.02.0028"),
]


# Egyptian primary-source (public domain): James Teackle Dennis's translation of
# "The Book of the Dead", and E. A. Wallis Budge's "Gods of the Egyptians",
# both on archive.org.
ARCHIVE_ORG: list[tuple[str, str]] = [
    ("The Gods of the Egyptians (Budge, 1904) — vol I",
     "https://archive.org/details/godsofegyptianss01budg"),
    ("The Gods of the Egyptians (Budge, 1904) — vol II",
     "https://archive.org/details/godsofegyptians02budg"),
    ("Egyptian Book of the Dead (Budge)",
     "https://archive.org/details/egyptianbookofde00budg"),
    ("Frazer, The Golden Bough (1922 abridged)",
     "https://archive.org/details/goldenboughstudy00fraz"),
    ("Bulfinch's Mythology",
     "https://archive.org/details/bulfinchsmytholo00bulf"),
]


def seed(dry_run: bool) -> dict:
    with get_db_session() as session:
        existing = {
            u.strip().lower()
            for u in session.execute(
                select(IngestionSource.url).where(IngestionSource.url.isnot(None))
            ).scalars().all() if u
        }

    inserted = 0
    by_bucket: dict[str, int] = {}

    def add_bucket(items, source_type, kind, year, cred):
        nonlocal inserted
        new = [(t, u) for t, u in items if u.lower() not in existing]
        by_bucket[kind] = len(new)
        if dry_run:
            for t, u in new[:10]:
                print(f"  [{kind}] {t:40s}  {u}")
            return
        if not new:
            return
        with get_db_session() as session:
            for title, url in new:
                session.add(IngestionSource(
                    source_type=source_type,
                    source_name=f"{title} ({kind})",
                    url=url,
                    language="en",
                    publication_year=year,
                    ingestion_status="pending",
                    peer_reviewed=True,
                    credibility_score=cred,
                    error_log=f"seeded from {kind}",
                ))
            session.commit()
        inserted += len(new)
        existing.update(u.lower() for _, u in new)

    add_bucket(THEOI, "primary_source", "theoi", 2000, 0.82)
    add_bucket(PERSEUS, "primary_source", "perseus", 1900, 0.90)
    add_bucket(ARCHIVE_ORG, "archive_org", "archive_pd_books", 1910, 0.85)

    return {"inserted": inserted, "by_bucket": by_bucket, "dry_run": dry_run}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    summary = seed(dry_run=args.dry_run)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
