import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.city_metrics import CityMetrics, utcnow
from app.schemas.analytics import (
    CityMetricsPublicRead,
    CityMetricsUpdate,
    CityMetricsVerwaltungRead,
)

logger = logging.getLogger(__name__)


async def get_city_metrics(
    session: AsyncSession, *, for_update: bool = False
) -> CityMetrics | None:
    statement = select(CityMetrics).order_by(CityMetrics.updated_at.desc()).limit(1)
    if for_update:
        statement = statement.with_for_update()
    return await session.scalar(statement)


def public_city_metrics(record: CityMetrics | None) -> CityMetricsPublicRead:
    if record is None:
        return CityMetricsPublicRead()
    return CityMetricsPublicRead(
        vacancy_rate=record.vacancy_rate,
        chain_store_rate=record.chain_store_rate,
        centrality_index=record.centrality_index,
        purchasing_power_index=record.purchasing_power_index,
        reference_date=record.reference_date,
        updated_at=record.updated_at,
    )


def verwaltung_city_metrics(record: CityMetrics | None) -> CityMetricsVerwaltungRead:
    public = public_city_metrics(record)
    return CityMetricsVerwaltungRead(
        **public.model_dump(),
        source=record.source if record else None,
        notes=record.notes if record else None,
        updated_by_user_id=(
            str(record.updated_by_user_id) if record and record.updated_by_user_id else None
        ),
    )


async def get_public_city_metrics(session: AsyncSession) -> CityMetricsPublicRead:
    return public_city_metrics(await get_city_metrics(session))


async def get_verwaltung_city_metrics(session: AsyncSession) -> CityMetricsVerwaltungRead:
    return verwaltung_city_metrics(await get_city_metrics(session))


async def update_city_metrics(
    session: AsyncSession,
    payload: CityMetricsUpdate,
    user_id: uuid.UUID,
) -> CityMetricsVerwaltungRead:
    record = await get_city_metrics(session, for_update=True)
    if record is None:
        record = CityMetrics()
        session.add(record)

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(record, field, value)
    record.updated_by_user_id = user_id
    record.updated_at = utcnow()
    await session.commit()
    await session.refresh(record)
    logger.info(
        "City metrics changed user_id=%s fields=%s",
        user_id,
        sorted(changes),
    )
    return verwaltung_city_metrics(record)
