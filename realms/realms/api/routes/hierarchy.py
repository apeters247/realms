"""Hierarchy API endpoints."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from realms.services.hierarchy_service import HierarchyService
from realms.utils.database import get_db_session

router = APIRouter()


@router.get("/tree")
async def get_hierarchy_tree(
    q: Optional[str] = Query(None),
    realm: Optional[str] = Query(None),
    culture_id: Optional[int] = Query(None, gt=0),
):
    with get_db_session() as session:
        service = HierarchyService(session)
        return {"data": service.get_hierarchy_tree(q=q, realm=realm, culture_id=culture_id)}


@router.get("/flat")
async def get_hierarchy_flat(
    q: Optional[str] = Query(None),
    realm: Optional[str] = Query(None),
    culture_id: Optional[int] = Query(None, gt=0),
):
    with get_db_session() as session:
        service = HierarchyService(session)
        return {"data": service.get_hierarchy_flat(q=q, realm=realm, culture_id=culture_id)}


@router.get("/path/{entity_id}")
async def get_entity_hierarchy_path(entity_id: int):
    with get_db_session() as session:
        service = HierarchyService(session)
        path = service.get_entity_hierarchy_path(entity_id)
        if path is None:
            raise HTTPException(status_code=404, detail="Entity not found")
        return {"data": path}
