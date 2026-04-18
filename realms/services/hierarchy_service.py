"""Service layer for hierarchy tree/flat queries."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from realms.models import Entity, EntityCategory, EntityClass


class HierarchyService:
    def __init__(self, session: Session):
        self.session = session

    def _filter_entities_stmt(
        self,
        q: Optional[str],
        realm: Optional[str],
        culture_id: Optional[int],
    ):
        stmt = select(Entity)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Entity.name.ilike(like), Entity.description.ilike(like)))
        if realm:
            stmt = stmt.where(Entity.realm == realm)
        return stmt

    def get_hierarchy_tree(
        self,
        q: Optional[str] = None,
        realm: Optional[str] = None,
        culture_id: Optional[int] = None,
    ) -> dict:
        entities = self.session.execute(
            self._filter_entities_stmt(q, realm, culture_id)
        ).scalars().all()

        class_ids = {e.entity_class_id for e in entities if e.entity_class_id is not None}
        classes: list[EntityClass] = []
        if class_ids:
            classes = list(
                self.session.execute(
                    select(EntityClass).where(EntityClass.id.in_(class_ids))
                ).scalars().all()
            )

        cat_ids = {c.category_id for c in classes if c.category_id is not None}
        categories: list[EntityCategory] = []
        if cat_ids:
            categories = list(
                self.session.execute(
                    select(EntityCategory).where(EntityCategory.id.in_(cat_ids))
                ).scalars().all()
            )

        entities_by_class: dict[int, list[Entity]] = {}
        for e in entities:
            if e.entity_class_id is not None:
                entities_by_class.setdefault(e.entity_class_id, []).append(e)

        classes_by_cat: dict[int, list[EntityClass]] = {}
        for c in classes:
            if c.category_id is not None:
                classes_by_cat.setdefault(c.category_id, []).append(c)

        tree_children = []
        for cat in sorted(categories, key=lambda x: x.name):
            cat_children = []
            for cls in sorted(classes_by_cat.get(cat.id, []), key=lambda x: x.name):
                class_entities = entities_by_class.get(cls.id, [])
                cat_children.append({
                    "id": cls.id,
                    "name": cls.name,
                    "type": "class",
                    "entity_count": len(class_entities),
                    "children": [
                        {
                            "id": e.id,
                            "name": e.name,
                            "type": "entity",
                            "entity_count": 0,
                            "children": [],
                            "meta": {"confidence": e.consensus_confidence or 0.0},
                        }
                        for e in sorted(class_entities, key=lambda x: x.name)
                    ],
                    "meta": {"confidence": cls.confidence_score or 0.0},
                })
            tree_children.append({
                "id": cat.id,
                "name": cat.name,
                "type": "category",
                "entity_count": sum(c["entity_count"] for c in cat_children),
                "children": cat_children,
                "meta": {},
            })

        return {"name": "root", "children": tree_children}

    def get_hierarchy_flat(
        self,
        q: Optional[str] = None,
        realm: Optional[str] = None,
        culture_id: Optional[int] = None,
    ) -> list[dict]:
        tree = self.get_hierarchy_tree(q=q, realm=realm, culture_id=culture_id)
        flat: list[dict] = []

        def walk(node: dict, path: list[str], level: int):
            if node.get("type") in {"category", "class", "entity"}:
                flat.append({
                    "id": node["id"],
                    "name": node["name"],
                    "level": level,
                    "path": path + [node["name"]],
                    "entity_count": node.get("entity_count", 0),
                    "confidence": node.get("meta", {}).get("confidence", 0.0),
                })
            for child in node.get("children", []):
                new_path = path + [node["name"]] if node.get("name") != "root" else path
                walk(child, new_path, level + 1)

        for child in tree["children"]:
            walk(child, [], 1)

        return flat

    def get_entity_hierarchy_path(self, entity_id: int) -> Optional[list[str]]:
        entity = self.session.get(Entity, entity_id)
        if entity is None:
            return None
        path: list[str] = []
        if entity.entity_class_id is not None:
            cls = self.session.get(EntityClass, entity.entity_class_id)
            if cls and cls.category_id is not None:
                cat = self.session.get(EntityCategory, cls.category_id)
                if cat:
                    path.append(cat.name)
            if cls:
                path.append(cls.name)
        path.append(entity.name)
        return path
