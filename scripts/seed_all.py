"""Massive ingestion bootstrap — seed every Wikipedia category in Tier 1+2 scope.

Walks a curated list of ~60 Wikipedia categories covering the full panoply of
classical religions, folk traditions, cryptids, and regional mythologies.
Each category is walked at depth 3 by ``seed_from_wikipedia_category``, with
the tier-3/4 blocklist already in place there.

Usage:
    python -m scripts.seed_all              # apply
    python -m scripts.seed_all --dry-run    # preview
    python -m scripts.seed_all --cap 100    # lower per-category cap

Exits when every category has been walked; prints a per-category summary.
"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time

log = logging.getLogger("realms.seed_all")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# Curated Tier 1 + Tier 2 Wikipedia categories. The tier-3/4 blocklist in
# seed_from_wikipedia_category.py scrubs inappropriate subcategories.
CATEGORIES: list[tuple[str, str]] = [
    # ─── DEITIES BY REGION/CULTURE ───
    ("Deities by continent", "region-deities"),
    ("African deities", "region-deities"),
    ("European deities", "region-deities"),
    ("Asian deities", "region-deities"),
    ("Oceanian deities", "region-deities"),
    ("American deities", "region-deities"),
    ("Mesoamerican deities", "region-deities"),
    ("Tutelary deities", "function-deities"),
    ("Death deities", "function-deities"),
    ("Solar deities", "function-deities"),
    ("Lunar deities", "function-deities"),
    ("Fertility deities", "function-deities"),
    ("Love and lust deities", "function-deities"),
    ("War deities", "function-deities"),
    ("Fire deities", "function-deities"),
    ("Water deities", "function-deities"),
    ("Sky and weather deities", "function-deities"),
    ("Earth and nature deities", "function-deities"),
    ("Trickster deities", "function-deities"),
    ("Creation deities", "function-deities"),
    ("Underworld deities", "function-deities"),
    ("Motherhood deities", "function-deities"),
    ("Smithing deities", "function-deities"),
    ("Wisdom deities", "function-deities"),

    # ─── ANCIENT PANTHEONS ───
    ("Greek gods", "pantheon-greek"),
    ("Greek goddesses", "pantheon-greek"),
    ("Roman gods", "pantheon-roman"),
    ("Roman goddesses", "pantheon-roman"),
    ("Egyptian gods", "pantheon-egyptian"),
    ("Egyptian goddesses", "pantheon-egyptian"),
    ("Mesopotamian deities", "pantheon-mesopotamian"),
    ("Sumerian deities", "pantheon-mesopotamian"),
    ("Akkadian deities", "pantheon-mesopotamian"),
    ("Norse gods", "pantheon-norse"),
    ("Norse goddesses", "pantheon-norse"),
    ("Celtic gods", "pantheon-celtic"),
    ("Celtic goddesses", "pantheon-celtic"),
    ("Slavic gods", "pantheon-slavic"),
    ("Slavic goddesses", "pantheon-slavic"),
    ("Hittite deities", "pantheon-hittite"),
    ("Etruscan gods", "pantheon-etruscan"),
    ("Canaanite deities", "pantheon-canaanite"),

    # ─── ASIAN PANTHEONS ───
    ("Hindu gods", "pantheon-hindu"),
    ("Hindu goddesses", "pantheon-hindu"),
    ("Devi", "pantheon-hindu"),
    ("Rigvedic deities", "pantheon-hindu"),
    ("Buddhist deities", "pantheon-buddhist"),
    ("Bodhisattvas", "pantheon-buddhist"),
    ("Taoist deities", "pantheon-taoist"),
    ("Chinese gods", "pantheon-chinese"),
    ("Japanese gods", "pantheon-japanese"),
    ("Kami", "pantheon-japanese"),
    ("Korean deities", "pantheon-korean"),

    # ─── INDIGENOUS / NATIVE ───
    ("Native American deities", "indigenous-americas"),
    ("Indigenous deities of North America", "indigenous-americas"),
    ("Aztec gods", "indigenous-americas"),
    ("Maya gods", "indigenous-americas"),
    ("Inca gods", "indigenous-americas"),
    ("Amazonian mythology", "indigenous-americas"),
    ("Yanomami mythology", "indigenous-americas"),

    # ─── AFRICAN & DIASPORA ───
    ("Yoruba gods", "pantheon-yoruba"),
    ("Orishas", "pantheon-yoruba"),
    ("Akan deities", "pantheon-akan"),
    ("Igbo deities", "pantheon-igbo"),
    ("Zulu deities", "pantheon-zulu"),
    ("Vodou", "diaspora-vodou"),
    ("Santería", "diaspora-santeria"),
    ("Candomblé", "diaspora-candomble"),

    # ─── SHAMANIC / SIBERIAN ───
    ("Siberian mythology", "shamanic"),
    ("Mongolian mythology", "shamanic"),
    ("Turkic mythology", "shamanic"),
    ("Tengrism", "shamanic"),

    # ─── LEGENDARY CREATURES / CRYPTIDS (TIER 2) ───
    ("Legendary creatures", "cryptids"),
    ("Legendary creatures by region", "cryptids"),
    ("European legendary creatures", "cryptids"),
    ("Asian legendary creatures", "cryptids"),
    ("African legendary creatures", "cryptids"),
    ("American legendary creatures", "cryptids"),
    ("Oceanian legendary creatures", "cryptids"),
    ("Japanese legendary creatures", "cryptids"),
    ("Chinese legendary creatures", "cryptids"),
    ("Irish legendary creatures", "cryptids"),
    ("Scottish legendary creatures", "cryptids"),
    ("Welsh legendary creatures", "cryptids"),
    ("Slavic legendary creatures", "cryptids"),
    ("Norse legendary creatures", "cryptids"),
    ("Philippine legendary creatures", "cryptids"),
    ("Korean legendary creatures", "cryptids"),
    ("Vietnamese legendary creatures", "cryptids"),
    ("Mesoamerican legendary creatures", "cryptids"),

    # ─── NATURE / FOLK SPIRITS ───
    ("Nature spirits", "spirits"),
    ("Household deities", "spirits"),
    ("Forest spirits", "spirits"),
    ("Water spirits", "spirits"),
    ("Fairies", "spirits-european"),

    # ─── ANCESTRAL / SAINTS (supplements Christian seed) ───
    ("Ancestor veneration", "ancestor"),
    ("Folk saints", "folk-saints"),
    ("Syncretism", "syncretism"),

    # ─── ANGELOLOGY / DEMONOLOGY (classical theological) ───
    ("Archangels", "angels"),
    ("Individual angels", "angels"),
    ("Demons", "demons"),
    ("Christian demons", "demons"),
    ("Jewish demons", "demons"),
    ("Islamic demons", "demons"),
    ("Zoroastrian demons", "demons"),

    # ─── PSYCHOPOMPS (classical) ───
    ("Psychopomps", "psychopomps"),
    ("Oracles", "oracles"),
]


def run_seed(category: str, depth: int, cap: int, dry_run: bool) -> int:
    """Shell out to seed_from_wikipedia_category. Returns insert count."""
    cmd = [
        sys.executable, "-m", "scripts.seed_from_wikipedia_category",
        "--category", category,
        "--depth", str(depth),
        "--max", str(cap),
    ]
    if dry_run:
        cmd.append("--dry-run")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        log.warning("seed timed out for %s", category)
        return 0
    out = (proc.stdout or "") + (proc.stderr or "")
    # Parse "inserted": N from the JSON tail.
    for line in out.splitlines()[::-1]:
        line = line.strip()
        if line.startswith('"inserted"'):
            try:
                return int(line.split(":", 1)[1].strip().rstrip(","))
            except (ValueError, IndexError):
                return 0
    return 0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--depth", type=int, default=3)
    p.add_argument("--cap", type=int, default=300)
    p.add_argument("--only-group", help="only categories with this group tag")
    args = p.parse_args()

    cats = [(c, g) for c, g in CATEGORIES if not args.only_group or g == args.only_group]
    log.info("seeding %d categories (dry-run=%s)", len(cats), args.dry_run)

    total_inserted = 0
    by_group: dict[str, int] = {}
    start = time.time()
    for i, (cat, group) in enumerate(cats, 1):
        n = run_seed(cat, args.depth, args.cap, args.dry_run)
        total_inserted += n
        by_group[group] = by_group.get(group, 0) + n
        log.info("[%d/%d] %-40s %s → %d inserted",
                 i, len(cats), cat, group, n)

    elapsed = time.time() - start
    log.info("complete: %d categories, %d total inserts, %.1fs",
             len(cats), total_inserted, elapsed)
    log.info("by group:")
    for g, n in sorted(by_group.items(), key=lambda x: -x[1]):
        log.info("  %-30s %d", g, n)


if __name__ == "__main__":
    main()
