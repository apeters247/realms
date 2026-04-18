"""
Hierarchy API Endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from realms.models.schemas import HierarchyTree, HierarchyFlat
from realms.services.hierarchy_service import HierarchyService
from realms.utils.database import get_db_session

router = APIRouter()

@router.get("/tree", response_model=HierarchyTree)
async def get_hierarchy_tree(
    q: Optional[str] = Query(None, description="Search to filter hierarchy"),
    realm: Optional[str] = Query(None, description="Filter by realm"),
    culture_id: Optional[int] = Query(None, gt=0)
):
    """Get full hierarchy tree for visualization"""
    try:
        with get_db_session() as session:
            service = HierarchyService(session)
            tree = service.get_hierarchy_tree(q=q, realm=realm, culture_id=culture_id)
            return {"data": tree}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flat", response_model=HierarchyFlat)
async def get_hierarchy_flat(
    q: Optional[str] = Query(None, description="Search to filter hierarchy"),
    realm: Optional[str] = Query(None, description="Filter by realm"),
    culture_id: Optional[int] = Query(None, gt=0)
):
    """Get hierarchy as flat list with levels"""
    try:
        with get_db_session() as session:
            service = HierarchyService(session)
            flat = service.get_hierarchy_flat(q=q, realm=realm, culture_id=culture_id)
            return {"data": flat}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/path/{entity_id}")
async def get_entity_hierarchy_path(entity_id: int):
    """Get the hierarchical path to a specific entity"""
    try:
        with get_db_session() as session:
            service = HierarchyService(session)
            path = service.get_entity_hierarchy_path(entity_id)
            if not path:
                raise HTTPException(status_code=404, detail="Entity not found")
            return {"data": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))