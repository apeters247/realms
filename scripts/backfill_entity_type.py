"""Rule-based backfill of NULL entity_type using description/powers/domains.

Many extractor runs produced entities with entity_type=None either because
the LLM returned an out-of-enum value (e.g. "realm", "myth") or omitted it.
This script scores each NULL-type entity against keyword patterns derived
from the existing ENTITY_TYPE_ENUM and writes the highest-scoring type
back. No LLM calls — purely text matching, free.

Usage:
    docker exec realms-api python -m scripts.backfill_entity_type
    docker exec realms-api python -m scripts.backfill_entity_type --apply
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from collections import Counter

from sqlalchemy import select

from realms.models import Entity
from realms.utils.database import get_db_session

log = logging.getLogger("realms.backfill_type")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# Whole-word signal sets. Tuned to ENTITY_TYPE_ENUM in extractor.py.
# Score = sum of matches; ties broken by the order below (later wins on tie
# so the more specific categories beat the more generic).
TYPE_SIGNALS: dict[str, list[str]] = {
    "deity": [
        r"\bgods?\b", r"\bgoddess(?:es)?\b", r"\bdeit(?:y|ies)\b",
        r"\bdivinit(?:y|ies)\b", r"\bdivine\b", r"\bpantheons?\b",
        r"\bsupreme being\b", r"\bcreator god\b",
        r"\b(?:sun|moon|sea|sky|war|love|wisdom|thunder|storm|harvest|fertility|death|wind|fire) gods?\b",
        r"\bmother goddess\b", r"\bfather god\b", r"\bking of the gods\b",
        r"\bavatar of\b", r"\bincarnation of\b",
        r"\borishas?\b", r"\bloa\b", r"\bkami\b", r"\bdevatā?\b", r"\bdevas?\b",
        r"\bworshipped as\b", r"\bvenerated as\b",
        r"\bpersonification of\b", r"\b(?:chief|patron|tutelary) (?:god|deity)\b",
    ],
    "nature_spirit": [
        r"\bnature spirits?\b", r"\bspirits? of (?:the )?(?:forest|water|river|mountain|sea|wind|fire|earth|sky|tree)s?\b",
        r"\bnymphs?\b", r"\bsprites?\b", r"\bfauns?\b", r"\bsatyrs?\b",
        r"\bfae\b", r"\bfair(?:y|ies)\b", r"\bfaer(?:y|ies)\b", r"\bsylphs?\b",
        r"\bdragons?\b", r"\bserpents?\b", r"\bsea monsters?\b",
        r"\btitans?\b", r"\bgiants?\b", r"\bdjinns?\b", r"\bjinns?\b",
        r"\bcryptids?\b", r"\blegendary creatures?\b", r"\bmythical creatures?\b",
        r"\bmythical beings?\b", r"\bmythological beings?\b",
        r"\btutelary spirits?\b", r"\bnature deit(?:y|ies)\b",
        r"\bwater spirits?\b", r"\bforest spirits?\b", r"\bmountain spirits?\b",
        r"\bfire spirits?\b", r"\bguardian spirits?\b",
        r"\belementals?\b", r"\b(?:elf|elves)\b", r"\bgnomes?\b",
        r"\btrolls?\b", r"\bogres?\b", r"\bgolems?\b",
        r"\bcentaurs?\b", r"\bmermaids?\b", r"\bmermen\b",
        r"\bspirits? (?:residing|dwelling|living)\b",
        r"\bfolkloric being\b", r"\bsupernatural beings?\b",
        r"\bphantasmal being\b", r"\bspirit being\b",
    ],
    "demonic": [
        r"\bdemons?\b", r"\bdemonic\b", r"\bdevils?\b",
        r"\bfallen angels?\b", r"\bevil spirits?\b", r"\bimps?\b",
        r"\bmalevolent (?:spirit|being)s?\b",
        r"\bsatan\b", r"\bsatanic\b", r"\babominations?\b",
        r"\binfernal\b", r"\bhellish\b", r"\bdemon princes?\b",
        r"\barchdemons?\b", r"\bsuccub(?:us|i)\b", r"\bincub(?:us|i)\b",
        r"\bdaevas?\b", r"\basuras?\b",
        r"\bspirit of evil\b", r"\bunclean spirit\b",
    ],
    "angelic": [
        r"\bangels?\b", r"\barchangels?\b", r"\bseraph(?:im|s)?\b",
        r"\bcherub(?:im|s)?\b",
        r"\bdominions?\b", r"\bpowers? of heaven\b",
        r"\bheavenly hosts?\b", r"\bguardian angels?\b",
        r"\bmalakh\b", r"\bmessengers? of god\b",
        r"\bnephilim\b",
    ],
    "ancestor": [
        r"\bancestors?\b", r"\bancestral spirits?\b",
        r"\bdeceased\b", r"\bspirits? of the dead\b",
        r"\bsaints?\b", r"\bmartyrs?\b", r"\bcanonized\b", r"\bbeatified\b",
        r"\bghosts?\b", r"\brevenants?\b",
        r"\bvenerated dead\b", r"\bbodhisattvas?\b",
        r"\bpopes?\b", r"\bblessed\b",
        r"\bspirit of (?:a|the) (?:deceased|dead|departed)\b",
        r"\bdeified mortal\b", r"\b(?:hero|heroine)\s+(?:cult|worship)\b",
    ],
    "human_specialist": [
        r"\bshamans?\b", r"\bshamaness(?:es)?\b", r"\bshamanic\b",
        r"\bpriests?\b", r"\bpriestess(?:es)?\b", r"\bhigh priests?\b",
        r"\bprophets?\b", r"\bprophetess(?:es)?\b", r"\boracles?\b",
        r"\bwitch(?:es)?\b", r"\bsorcerers?\b", r"\bsorceress(?:es)?\b",
        r"\bmagicians?\b", r"\bmagi\b", r"\bdruids?\b",
        r"\bmystics?\b", r"\bseers?\b", r"\bdiviners?\b",
        r"\bhealers?\b", r"\bmedicine (?:man|woman|men|women)\b",
        r"\bcurander(?:o|a|os|as)\b", r"\bayahuasquer(?:o|a|os|as)\b",
        r"\bspiritual practitioner\b",
    ],
    "animal_ally": [
        r"\banimal all(?:y|ies)\b", r"\banimal spirits?\b", r"\bspirit animals?\b",
        r"\btotems?(?:\s+animals?)?\b", r"\banimal guides?\b",
        r"\bsacred animals?\b", r"\bshapeshifters?\b",
        r"\bcompanion animals?\b", r"\banimal totems?\b",
    ],
    "plant_spirit": [
        r"\bplant spirits?\b", r"\bplant teachers?\b", r"\bsacred plants?\b",
        r"\bayahuasca\b", r"\bpeyote\b", r"\bsoma\b",
        r"\bsalvia\b", r"\bsanto daime\b",
        r"\bspirits? of (?:the )?plants?\b",
    ],
}

# Tie-break priority: when multiple types tie, prefer in this order
# (more specific / less common wins).
PRIORITY = [
    "plant_spirit", "animal_ally", "angelic",
    "demonic", "ancestor", "human_specialist",
    "nature_spirit", "deity",
]
_PRIO_INDEX = {t: i for i, t in enumerate(PRIORITY)}


# Compile once
_COMPILED = {
    t: [re.compile(p, re.IGNORECASE) for p in pats]
    for t, pats in TYPE_SIGNALS.items()
}


def _haystack(e: Entity) -> str:
    parts: list[str] = []
    if e.description:
        parts.append(e.description)
    if e.powers and isinstance(e.powers, list):
        parts.append(" ".join(str(p) for p in e.powers))
    if e.domains and isinstance(e.domains, list):
        parts.append(" ".join(str(d) for d in e.domains))
    if e.alternate_names and isinstance(e.alternate_names, dict):
        for v in e.alternate_names.values():
            if isinstance(v, list):
                parts.append(" ".join(str(x) for x in v))
    return " \n ".join(parts).lower()


def classify(e: Entity) -> str | None:
    text = _haystack(e)
    if not text:
        return None
    scores: Counter[str] = Counter()
    for t, regexes in _COMPILED.items():
        for r in regexes:
            if r.search(text):
                scores[t] += 1
    if not scores:
        return None
    best = max(scores.items(), key=lambda kv: (kv[1], _PRIO_INDEX[kv[0]]))
    return best[0]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--limit", type=int, default=0,
                   help="optional cap (0 = all)")
    args = p.parse_args()

    with get_db_session() as session:
        q = select(Entity).where(Entity.entity_type.is_(None))
        if args.limit:
            q = q.limit(args.limit)
        rows = session.execute(q).scalars().all()
        log.info("Found %d entities with entity_type=NULL", len(rows))

        outcomes: Counter[str] = Counter()
        examples: dict[str, list[str]] = {}
        changed = 0

        for e in rows:
            cls = classify(e)
            outcomes[cls or "UNCLASSIFIED"] += 1
            if cls and len(examples.setdefault(cls, [])) < 4:
                examples[cls].append(e.name)
            if cls and args.apply:
                e.entity_type = cls
                changed += 1

        if args.apply:
            session.commit()

        log.info("Outcomes: %s", dict(outcomes))
        for t, names in examples.items():
            log.info("  %s e.g. %s", t, names)
        log.info("Would-change: %d (dry-run=%s)", sum(v for k, v in outcomes.items() if k != "UNCLASSIFIED"), not args.apply)
        print(json.dumps({
            "null_input_entities": len(rows),
            "outcomes": dict(outcomes),
            "applied": args.apply,
            "examples": examples,
        }, indent=2))


if __name__ == "__main__":
    main()
