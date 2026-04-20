"""Stream U — curated collections (thematic groupings of entities).

Collections are defined declaratively in ``COLLECTIONS`` below; each describes
a filter rule that's applied over the live entity corpus. New collections can
be added by extending the list. The build-time web loader queries these
endpoints to render the ``/collections`` index + ``/collection/[slug]`` pages.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import APIRouter, HTTPException
from sqlalchemy import String, or_, select, text
from sqlalchemy.dialects.postgresql import JSONB

from realms.models import Entity
from realms.utils.database import get_db_session

router = APIRouter()


@dataclass
class Collection:
    slug: str
    title: str
    subtitle: str
    description: str
    # SQL filter applied to `select(Entity)` — receives the statement.
    apply_filter: Callable[[any], any]


def _has_domain_token(tokens: list[str]):
    """Filter: entity.domains JSONB contains any token, case-insensitive.

    Implemented via `to_jsonb(domains)::text ILIKE '%token%'` — for small
    corpora (<10k entities) this is fast enough and avoids needing a GIN
    trigram index on JSONB-to-text.
    """
    def _apply(stmt):
        clauses = []
        for i, t in enumerate(tokens):
            key = f"dom_{i}"
            clauses.append(
                text(f"lower(domains::text) LIKE :{key}").bindparams(**{key: f"%{t.lower()}%"})
            )
        return stmt.where(or_(*clauses))
    return _apply


def _has_type_in(types: list[str]):
    def _apply(stmt):
        return stmt.where(Entity.entity_type.in_(types))
    return _apply


def _has_realm_in(realms: list[str]):
    def _apply(stmt):
        return stmt.where(Entity.realm.in_(realms))
    return _apply


def _compose(*filters):
    def _apply(stmt):
        for f in filters:
            stmt = f(stmt)
        return stmt
    return _apply


COLLECTIONS: list[Collection] = [
    Collection(
        slug="solar-deities",
        title="Solar Deities",
        subtitle="Gods and spirits of the sun across traditions",
        description=(
            "Entities whose domain or realm ties them to the sun: solar disks, "
            "sky-piercing travelers, dawn-bringers, noon-burning judges. "
            "Ra, Helios, Surya, Amaterasu, Inti, Huitzilopochtli, and kindred."
        ),
        apply_filter=_has_domain_token(["sun", "solar", "dawn", "sunrise", "sunset", "daylight"]),
    ),
    Collection(
        slug="lunar-deities",
        title="Lunar Deities",
        subtitle="Moon-governors, cycle-keepers, tidal powers",
        description=(
            "Entities associated with the moon, its phases, and tidal cycles: "
            "Selene, Chandra, Tsukuyomi, Khonsu, Mama Killa, Ix Chel."
        ),
        apply_filter=_has_domain_token(["moon", "lunar", "tide"]),
    ),
    Collection(
        slug="death-psychopomps",
        title="Psychopomps & Death Gods",
        subtitle="Escorts and sovereigns of the dead",
        description=(
            "Entities who rule, attend, or guide the dead: Anubis, Hermes, "
            "Yama, Hel, Mictlantecuhtli, and the tradition-specific escorts of souls."
        ),
        apply_filter=_compose(
            _has_domain_token(["death", "dead", "underworld", "afterlife", "soul", "funeral", "mourn"]),
        ),
    ),
    Collection(
        slug="forest-spirits",
        title="Forest & Woodland Spirits",
        subtitle="Guardians of trees, groves, and wild thickets",
        description=(
            "Spirits of forest and wilderness: chullachaqui, leshy, curupira, kodama, "
            "dryads — entities embedded in non-human ecosystems their cultures still share."
        ),
        apply_filter=_has_realm_in(["forest"]),
    ),
    Collection(
        slug="water-spirits",
        title="Water Spirits",
        subtitle="River, lake, ocean, and rainfall powers",
        description=(
            "Entities tied to bodies of water: Mami Wata, yumbo, Yemoja, Sirona, "
            "Thetis, river-gods and lake-mothers worldwide."
        ),
        apply_filter=_has_realm_in(["water"]),
    ),
    Collection(
        slug="household-deities",
        title="Household & Hearth Spirits",
        subtitle="Guardians of home, family, and domestic continuity",
        description=(
            "Lares, domovoi, nats, kamidana spirits, brownies — entities who live in "
            "and protect human dwellings, often in exchange for small daily offerings."
        ),
        apply_filter=_has_domain_token(["home", "hearth", "household", "family", "domestic"]),
    ),
    Collection(
        slug="trickster-gods",
        title="Tricksters",
        subtitle="Rule-breakers, shape-shifters, and culture heroes",
        description=(
            "Entities who subvert order to teach it: Anansi, Coyote, Loki, Eshu, "
            "Raven, Maui, Monkey — each laughs at the rules of their tradition while "
            "reinforcing them."
        ),
        apply_filter=_has_domain_token(["trick", "cunning", "mischief", "deception", "theft"]),
    ),
    Collection(
        slug="ancestor-classes",
        title="Ancestors",
        subtitle="Veneration of lineage and the named dead",
        description=(
            "Entities who are or were once human and whose memory is ritually sustained: "
            "aiyekoto, lares familiares, Xapiripë ancestor spirits, ancestral Kamigami."
        ),
        apply_filter=_has_type_in(["ancestor"]),
    ),
    Collection(
        slug="cryptids-and-creatures",
        title="Cryptids & Legendary Creatures",
        subtitle="Regional folk beings and wild unseen things",
        description=(
            "Tier 2 — named creatures documented in folk belief: wendigos, jiangshi, "
            "aswangs, kelpies, leshys, chupacabras recorded within culturally-attested "
            "traditions. Excludes modern fictional entities."
        ),
        apply_filter=_has_type_in(["animal_ally", "nature_spirit"]),
    ),
    Collection(
        slug="ambiguous-beings",
        title="Neither Good Nor Evil",
        subtitle="Entities whose alignment resists binary labels",
        description=(
            "Many traditions resist the good/evil binary. These are the entities "
            "explicitly characterised as ambiguous — helpful and dangerous by turns, "
            "depending on reciprocity."
        ),
        apply_filter=lambda stmt: stmt.where(Entity.alignment == "ambiguous"),
    ),
]


def _members_for(col: Collection, limit: int = 100):
    with get_db_session() as session:
        stmt = (
            select(Entity)
            .where(Entity.review_status != "rejected")
            .order_by(Entity.consensus_confidence.desc().nulls_last(), Entity.name)
            .limit(limit)
        )
        stmt = col.apply_filter(stmt)
        rows = session.execute(stmt).scalars().all()
        return [
            {
                "id": r.id, "name": r.name, "entity_type": r.entity_type,
                "alignment": r.alignment, "realm": r.realm,
                "consensus_confidence": float(r.consensus_confidence or 0.0),
                "cultural_associations": r.cultural_associations or [],
            }
            for r in rows
        ]


@router.get("/")
async def list_collections():
    out = []
    with get_db_session() as session:
        for col in COLLECTIONS:
            stmt = select(Entity).where(Entity.review_status != "rejected")
            stmt = col.apply_filter(stmt)
            count = session.execute(stmt).scalars().all()
            out.append({
                "slug": col.slug,
                "title": col.title,
                "subtitle": col.subtitle,
                "description": col.description,
                "n_members": len(count),
            })
    return {"data": out}


@router.get("/{slug}")
async def get_collection(slug: str):
    col = next((c for c in COLLECTIONS if c.slug == slug), None)
    if col is None:
        raise HTTPException(status_code=404, detail=f"no collection '{slug}'")
    members = _members_for(col, limit=200)
    return {"data": {
        "slug": col.slug,
        "title": col.title,
        "subtitle": col.subtitle,
        "description": col.description,
        "n_members": len(members),
        "members": members,
    }}
