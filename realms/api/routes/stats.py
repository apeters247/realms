"""Statistics API endpoints."""
from fastapi import APIRouter

from realms.services.stats_service import StatsService
from realms.utils.database import get_db_session

router = APIRouter()


@router.get("/")
async def get_stats():
    with get_db_session() as session:
        service = StatsService(session)
        return {"data": service.get_stats()}
