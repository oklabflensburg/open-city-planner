from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.statistics import StatisticsDataSourceStatus
from app.services.area_statistics import statistics_source_status

router = APIRouter(prefix="/data-sources", tags=["Statistics"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get(
    "/status",
    response_model=list[StatisticsDataSourceStatus],
    summary="Status öffentlicher Datenquellen anzeigen",
)
async def get_data_source_status(session: SessionDep) -> list[StatisticsDataSourceStatus]:
    return [await statistics_source_status(session)]
