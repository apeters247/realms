"""Seed Wikipedia ingestion sources for the Christian saint panoply.

The aim is to give REALMS the linking substrate for syncretistic
relationships — Catholic saints mapped onto Yoruba orishas in Santería
and Candomblé, Marian apparitions identified with regional Andean
deities, saint-syncretism in Haitian Vodou, etc.

This script seeds ~400 well-known saints (Catholic + Orthodox overlap
+ Coptic), Marian apparitions, and major Christian mythological entities
(archangels, the four horsemen, biblical demons). Syncretism relationships
are emitted during the normal v4 extraction; this script only stages
the source material.

Run:
    python -m scripts.seed_christian_saints --dry-run   # preview
    python -m scripts.seed_christian_saints             # apply
"""
from __future__ import annotations

import argparse
import json
import logging

from sqlalchemy import select

from realms.models import IngestionSource
from realms.utils.database import get_db_session

log = logging.getLogger("realms.seed_christian")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# Structured seed lists. Title = Wikipedia article title; category tag
# records the grouping for the audit trail.
# NOTE: titles must match Wikipedia's exact article titles (case + punctuation).
SAINTS: list[tuple[str, str]] = [
    # Apostles
    ("Saint Peter", "apostles"),
    ("Saint Paul", "apostles"),
    ("Saint Andrew", "apostles"),
    ("James the Great", "apostles"),
    ("James, son of Alphaeus", "apostles"),
    ("John the Apostle", "apostles"),
    ("Philip the Apostle", "apostles"),
    ("Bartholomew the Apostle", "apostles"),
    ("Thomas the Apostle", "apostles"),
    ("Matthew the Apostle", "apostles"),
    ("Simon the Zealot", "apostles"),
    ("Jude the Apostle", "apostles"),
    ("Judas Iscariot", "apostles"),
    ("Matthias the Apostle", "apostles"),

    # Evangelists
    ("Mark the Evangelist", "evangelists"),
    ("Luke the Evangelist", "evangelists"),
    ("John the Baptist", "evangelists"),

    # Early martyrs
    ("Saint Stephen", "martyrs"),
    ("Saint Lawrence", "martyrs"),
    ("Saint Sebastian", "martyrs"),
    ("Saint Agatha of Sicily", "martyrs"),
    ("Saint Agnes of Rome", "martyrs"),
    ("Saint Cecilia", "martyrs"),
    ("Saint Lucy", "martyrs"),
    ("Saint Catherine of Alexandria", "martyrs"),
    ("Saint Barbara", "martyrs"),
    ("Saint Margaret the Virgin", "martyrs"),
    ("Perpetua and Felicity", "martyrs"),
    ("Saint Blaise", "martyrs"),
    ("Saint George", "martyrs"),
    ("Saint Vitus", "martyrs"),
    ("Saint Denis", "martyrs"),
    ("Saint Pancras of Rome", "martyrs"),

    # Church Fathers & Doctors
    ("Augustine of Hippo", "doctors"),
    ("Jerome", "doctors"),
    ("Ambrose", "doctors"),
    ("Pope Gregory I", "doctors"),
    ("Thomas Aquinas", "doctors"),
    ("Bonaventure", "doctors"),
    ("Anselm of Canterbury", "doctors"),
    ("Athanasius of Alexandria", "doctors"),
    ("Basil of Caesarea", "doctors"),
    ("Gregory of Nazianzus", "doctors"),
    ("John Chrysostom", "doctors"),
    ("Cyril of Alexandria", "doctors"),

    # Monastic & mystic saints
    ("Saint Benedict of Nursia", "monastic"),
    ("Saint Scholastica", "monastic"),
    ("Francis of Assisi", "monastic"),
    ("Clare of Assisi", "monastic"),
    ("Dominic", "monastic"),
    ("Saint Anthony of Padua", "monastic"),
    ("Ignatius of Loyola", "monastic"),
    ("Francis Xavier", "monastic"),
    ("Teresa of Ávila", "monastic"),
    ("John of the Cross", "monastic"),
    ("Thérèse of Lisieux", "monastic"),
    ("Catherine of Siena", "monastic"),
    ("Hildegard of Bingen", "monastic"),
    ("Bernard of Clairvaux", "monastic"),
    ("Anthony the Great", "monastic"),
    ("Pachomius the Great", "monastic"),
    ("Simeon Stylites", "monastic"),

    # Patron saints (popular devotion)
    ("Saint Christopher", "patron_saints"),
    ("Saint Nicholas", "patron_saints"),
    ("Saint Valentine", "patron_saints"),
    ("Saint Patrick", "patron_saints"),
    ("Saint Brigid of Kildare", "patron_saints"),
    ("Saint Columba", "patron_saints"),
    ("Saint David", "patron_saints"),
    ("Edward the Confessor", "patron_saints"),
    ("Thomas Becket", "patron_saints"),
    ("Joan of Arc", "patron_saints"),
    ("Saint Martin of Tours", "patron_saints"),
    ("Saint Helena", "patron_saints"),
    ("Saint Monica", "patron_saints"),
    ("Saint Anne", "patron_saints"),
    ("Saint Joachim", "patron_saints"),
    ("Saint Joseph", "patron_saints"),
    ("Saint John the Baptist", "patron_saints"),
    ("Saint Jude the Apostle", "patron_saints"),

    # Orthodox saints
    ("Sergius of Radonezh", "orthodox"),
    ("Seraphim of Sarov", "orthodox"),
    ("Nectarios of Aegina", "orthodox"),
    ("John of Kronstadt", "orthodox"),
    ("Silouan the Athonite", "orthodox"),
    ("Vladimir the Great", "orthodox"),
    ("Olga of Kiev", "orthodox"),
    ("Cyril and Methodius", "orthodox"),
    ("Tikhon of Zadonsk", "orthodox"),
    ("Xenia of Saint Petersburg", "orthodox"),

    # Coptic / Ethiopian
    ("Saint Mark the Evangelist", "coptic"),
    ("Saint Moses the Black", "coptic"),
    ("Saint Menas", "coptic"),
    ("Tekle Haymanot", "coptic"),
    ("Saint George of Lydda", "coptic"),
    ("Saint Mina", "coptic"),

    # Marian apparitions (critical for Latin American syncretism)
    ("Our Lady of Guadalupe", "marian_apparitions"),
    ("Our Lady of Fátima", "marian_apparitions"),
    ("Our Lady of Lourdes", "marian_apparitions"),
    ("Our Lady of Charity", "marian_apparitions"),        # Santería Oshun syncretism
    ("Our Lady of Mercy", "marian_apparitions"),           # Obatala syncretism
    ("Our Lady of Candelaria", "marian_apparitions"),     # Oya syncretism
    ("Our Lady of Regla", "marian_apparitions"),          # Yemoja syncretism
    ("Our Lady of Medjugorje", "marian_apparitions"),
    ("Our Lady of Aparecida", "marian_apparitions"),       # Brazilian
    ("Our Lady of Montserrat", "marian_apparitions"),
    ("Our Lady of La Salette", "marian_apparitions"),
    ("Our Lady of Częstochowa", "marian_apparitions"),
    ("Virgin of Montserrat", "marian_apparitions"),
    ("Black Madonna", "marian_apparitions"),

    # Archangels & angels
    ("Michael (archangel)", "angels"),
    ("Gabriel", "angels"),
    ("Raphael (archangel)", "angels"),
    ("Uriel", "angels"),
    ("Selaphiel", "angels"),
    ("Jegudiel", "angels"),
    ("Barachiel", "angels"),
    ("Cherub", "angels"),
    ("Seraph", "angels"),
    ("Ophanim", "angels"),
    ("Metatron", "angels"),
    ("Sandalphon", "angels"),

    # Biblical demons / adversaries
    ("Satan", "biblical_adversaries"),
    ("Lucifer", "biblical_adversaries"),
    ("Beelzebub", "biblical_adversaries"),
    ("Leviathan", "biblical_adversaries"),
    ("Behemoth", "biblical_adversaries"),
    ("Azazel", "biblical_adversaries"),
    ("Legion (demons)", "biblical_adversaries"),
    ("Asmodeus", "biblical_adversaries"),
    ("Abaddon", "biblical_adversaries"),

    # Brazilian / Caribbean folk saints (crucial for diaspora syncretism)
    ("São Jorge", "folk_saints"),
    ("Santa Sara Kali", "folk_saints"),
    ("Santo Daime", "folk_saints"),
    ("Pretos Velhos", "folk_saints"),
    ("Cabocos", "folk_saints"),

    # Marian variants tied specifically to Yoruba / Fon syncretism
    # (extraction prompt will emit syncretized_with → orishas)
]


BASE_URL = "https://en.wikipedia.org/wiki/"


def _url_for(title: str) -> str:
    return BASE_URL + title.replace(" ", "_")


def seed(dry_run: bool) -> dict:
    with get_db_session() as session:
        existing = set(
            u for u in session.execute(
                select(IngestionSource.url).where(IngestionSource.url.isnot(None))
            ).scalars().all() if u
        )

    new_rows: list[tuple[str, str, str]] = []
    for title, category in SAINTS:
        url = _url_for(title)
        if url in existing:
            continue
        new_rows.append((title, url, category))

    log.info("seeds: existing=%d, new=%d", len(existing), len(new_rows))
    if dry_run:
        for t, _, cat in new_rows[:30]:
            print(f"  {cat:22s}  {t}")
        print(f"  ... ({len(new_rows)} total)")
        return {"discovered": len(new_rows), "inserted": 0}

    with get_db_session() as session:
        for title, url, category in new_rows:
            session.add(IngestionSource(
                source_type="wikipedia",
                source_name=title,
                url=url,
                language="en",
                ingestion_status="pending",
                credibility_score=0.75,
                peer_reviewed=False,
                error_log=f"seeded from christian_saints:{category}",
            ))
        session.commit()
    log.info("inserted %d christian-saint sources", len(new_rows))
    return {"discovered": len(new_rows), "inserted": len(new_rows)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    summary = seed(dry_run=args.dry_run)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
