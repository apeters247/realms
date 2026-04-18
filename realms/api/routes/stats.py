"""Statistics API endpoints."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_stats():
    """Stub: replaced in Task 15."""
    return {"data": {
        "total_entities": 0,
        "by_type": {},
        "by_realm": {},
        "by_alignment": {},
        "by_culture": {},
        "avg_confidence": 0.0,
        "sources_processed": 0,
        "total_extractions": 0,
    }}
