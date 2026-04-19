"""Relationship-graph endpoint: returns nodes + edges for a Cytoscape.js view."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import and_, or_, select

from realms.models import Entity, EntityRelationship
from realms.utils.database import get_db_session

router = APIRouter()


SEMANTIC_TYPES = {
    "parent_of", "child_of", "consort_of", "sibling_of", "allied_with",
    "enemy_of", "teacher_of", "student_of", "serves", "ruled_by",
    "manifests_as", "aspect_of", "syncretized_with", "created_by",
}


@router.get("/ego/{center_id}")
async def ego_graph(
    center_id: int,
    depth: int = Query(2, ge=1, le=4),
    max_nodes: int = Query(150, ge=10, le=500),
    semantic_only: bool = Query(True),
):
    """Breadth-first neighborhood around one entity.

    ``depth=1`` returns the immediate neighbors; ``depth=2`` adds their neighbors,
    etc. Semantic edges are prioritized; co_occurrence edges are included only
    if ``semantic_only=False``.
    """
    with get_db_session() as session:
        edge_q = select(EntityRelationship)
        if semantic_only:
            edge_q = edge_q.where(EntityRelationship.relationship_type.in_(list(SEMANTIC_TYPES)))
        all_edges = list(session.execute(edge_q).scalars().all())

        # Build adjacency
        adj: dict[int, list[EntityRelationship]] = {}
        for e in all_edges:
            adj.setdefault(e.source_entity_id, []).append(e)
            adj.setdefault(e.target_entity_id, []).append(e)

        # BFS from center
        visited: set[int] = {center_id}
        frontier = [center_id]
        picked_edges: list[EntityRelationship] = []
        for _ in range(depth):
            next_frontier: list[int] = []
            for node in frontier:
                for edge in adj.get(node, []):
                    other = edge.target_entity_id if edge.source_entity_id == node else edge.source_entity_id
                    if len(visited) >= max_nodes:
                        break
                    if other not in visited:
                        visited.add(other)
                        next_frontier.append(other)
                    if edge not in picked_edges:
                        picked_edges.append(edge)
                if len(visited) >= max_nodes:
                    break
            frontier = next_frontier
            if len(visited) >= max_nodes:
                break

        entities = list(session.execute(
            select(Entity).where(Entity.id.in_(visited))
        ).scalars().all())

        nodes = [{
            "data": {
                "id": str(e.id),
                "label": e.name,
                "entity_type": e.entity_type,
                "alignment": e.alignment,
                "realm": e.realm,
                "confidence": e.consensus_confidence or 0.0,
                "cultural_associations": e.cultural_associations or [],
                "is_center": e.id == center_id,
            },
        } for e in entities]
        edges = [{
            "data": {
                "id": f"e{e.id}",
                "source": str(e.source_entity_id),
                "target": str(e.target_entity_id),
                "rel_type": e.relationship_type,
                "confidence": e.extraction_confidence or 0.0,
                "is_semantic": e.relationship_type in SEMANTIC_TYPES,
            },
        } for e in picked_edges]
        return {
            "data": {
                "nodes": nodes, "edges": edges,
                "stats": {
                    "node_count": len(nodes),
                    "edge_count": len(edges),
                    "center_id": center_id,
                    "depth": depth,
                },
            }
        }


@router.get("/")
async def graph(
    culture: Optional[str] = Query(None, description="Filter entities by cultural_associations name"),
    rel_type: Optional[str] = Query(None,
        description="A specific relationship_type, or 'semantic' for any semantic edge"),
    max_nodes: int = Query(250, ge=10, le=1000),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
):
    """Return nodes + edges suitable for Cytoscape.js.

    Priority order: semantic edges first (e.g. parent_of), then co_occurrence as
    space remains. Nodes are pulled from edges and then supplemented with any
    culture-matching entities up to ``max_nodes``.
    """
    with get_db_session() as session:
        edge_q = select(EntityRelationship)
        if rel_type == "semantic":
            edge_q = edge_q.where(EntityRelationship.relationship_type.in_(list(SEMANTIC_TYPES)))
        elif rel_type:
            edge_q = edge_q.where(EntityRelationship.relationship_type == rel_type)
        if min_confidence > 0:
            edge_q = edge_q.where(EntityRelationship.extraction_confidence >= min_confidence)

        all_edges = list(session.execute(edge_q).scalars().all())
        # Prefer semantic edges
        semantic = [e for e in all_edges if e.relationship_type in SEMANTIC_TYPES]
        weak = [e for e in all_edges if e.relationship_type not in SEMANTIC_TYPES]

        # Budget: pick edges so that total unique node count stays <= max_nodes
        picked_edges: list[EntityRelationship] = []
        node_ids: set[int] = set()
        for e in semantic + weak:
            if e.source_entity_id in node_ids and e.target_entity_id in node_ids:
                picked_edges.append(e)
                continue
            needed = 0
            if e.source_entity_id not in node_ids:
                needed += 1
            if e.target_entity_id not in node_ids:
                needed += 1
            if len(node_ids) + needed > max_nodes:
                break
            node_ids.add(e.source_entity_id)
            node_ids.add(e.target_entity_id)
            picked_edges.append(e)

        # Pull entity details for nodes (optionally filter by culture)
        entities_q = select(Entity).where(Entity.id.in_(node_ids))
        entities = list(session.execute(entities_q).scalars().all())
        if culture:
            entities = [
                e for e in entities
                if culture in (e.cultural_associations or [])
            ]
            kept_ids = {e.id for e in entities}
            picked_edges = [
                e for e in picked_edges
                if e.source_entity_id in kept_ids and e.target_entity_id in kept_ids
            ]

        # Build cytoscape payload
        nodes = [{
            "data": {
                "id": str(e.id),
                "label": e.name,
                "entity_type": e.entity_type,
                "alignment": e.alignment,
                "realm": e.realm,
                "confidence": e.consensus_confidence or 0.0,
                "cultural_associations": e.cultural_associations or [],
            },
        } for e in entities]
        edges = [{
            "data": {
                "id": f"e{e.id}",
                "source": str(e.source_entity_id),
                "target": str(e.target_entity_id),
                "rel_type": e.relationship_type,
                "confidence": e.extraction_confidence or 0.0,
                "is_semantic": e.relationship_type in SEMANTIC_TYPES,
            },
        } for e in picked_edges]

        return {
            "data": {
                "nodes": nodes,
                "edges": edges,
                "stats": {
                    "node_count": len(nodes),
                    "edge_count": len(edges),
                    "semantic_edges": sum(1 for e in picked_edges if e.relationship_type in SEMANTIC_TYPES),
                    "weak_edges": sum(1 for e in picked_edges if e.relationship_type not in SEMANTIC_TYPES),
                },
            }
        }
