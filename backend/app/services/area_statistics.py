from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.keys import build_cache_key
from app.cache.service import cache_service
from app.core.config import get_settings
from app.platform.modules.sdk import StatisticsArea, StatisticsSelection
from app.schemas.statistics import (
    AreaStatisticSeriesRead,
    AreaStatisticsRead,
    StatisticsDataSourceStatus,
)
from app.services.cache_versions import cache_version
from app.services.flensburg_statistics_import import DASHBOARD_URL, LICENSE, SOURCE


def _relative(value: Decimal | None, reference: Decimal | None) -> Decimal | None:
    if value is None or reference in {None, Decimal(0)}:
        return None
    return ((value - reference) / reference * 100).quantize(Decimal("0.01"))


async def _mapping_context(
    session: AsyncSession, selection: StatisticsSelection
) -> dict | None:
    row = (
        await session.execute(
            text("""
              SELECT target.id AS statistics_id,
                     municipality.id AS municipality_id
              FROM external_area_mappings target
              JOIN external_area_mappings municipality
                ON municipality.source=target.source
              WHERE target.source=:source
                AND target.external_area_name=:target_name
                AND target.level=:target_level
                AND municipality.external_area_name=:municipality_name
                AND municipality.level=:municipality_level
              LIMIT 1
            """),
            {
                "source": SOURCE,
                "target_name": selection.target.name,
                "target_level": selection.target.area_type,
                "municipality_name": selection.municipality.name,
                "municipality_level": selection.municipality.area_type,
            },
        )
    ).mappings().first()
    return dict(row) if row else None


async def _source(session: AsyncSession) -> dict | None:
    row = (
        await session.execute(
            text("""
              SELECT max(last_import_at) AS last_import_at,
                     max(source_updated_at) AS source_updated_at
              FROM statistical_datasets WHERE source=:source
            """),
            {"source": SOURCE},
        )
    ).mappings().first()
    if not row or row["last_import_at"] is None:
        return None
    return {
        "name": "Stadt Flensburg – Zahlenspiegel",
        "url": DASHBOARD_URL,
        "license": LICENSE,
        **dict(row),
    }


def _reference(value: StatisticsArea) -> dict:
    return {
        "id": value.id,
        "slug": value.slug,
        "name": value.name,
        "area_type": value.area_type,
    }


async def _area_statistics_uncached(
    session: AsyncSession, selection: StatisticsSelection
) -> AreaStatisticsRead | None:
    context = await _mapping_context(session, selection)
    if context is None:
        return None
    rows = (
        await session.execute(
            text("""
              WITH ranked AS (
                SELECT observation.*,row_number() OVER (
                  PARTITION BY observation.metric_id ORDER BY observation.period_start DESC
                ) AS rank
                FROM statistical_observations observation
                WHERE observation.statistical_area_id=:statistics_id
              )
              SELECT metric.key,metric.name,metric.category,metric.unit,
                     ranked.value_numeric,ranked.period_start,ranked.is_calculated,
                     city.value_numeric AS municipality_value
              FROM ranked JOIN statistical_metrics metric ON metric.id=ranked.metric_id
              LEFT JOIN statistical_observations city
                ON city.metric_id=ranked.metric_id
               AND city.statistical_area_id=:municipality_id
               AND city.period_start=ranked.period_start
              WHERE ranked.rank=1 AND metric.public=true
              ORDER BY CASE metric.category
                WHEN 'Bevölkerung' THEN 1 WHEN 'Altersstruktur' THEN 2
                WHEN 'Haushalte' THEN 3 ELSE 4 END,metric.name
            """),
            {
                "statistics_id": context["statistics_id"],
                "municipality_id": context["municipality_id"],
            },
        )
    ).mappings().all()
    latest = []
    for row in rows:
        value = row["value_numeric"]
        municipality = row["municipality_value"]
        latest.append(
            {
                "key": row["key"],
                "name": row["name"],
                "category": row["category"],
                "value": value,
                "unit": row["unit"],
                "period": str(row["period_start"].year),
                "period_start": row["period_start"],
                "area_level": selection.target.area_type,
                "is_calculated": row["is_calculated"],
                "municipality_value": municipality,
                "difference": value - municipality
                if value is not None and municipality is not None
                else None,
                "relative_difference": _relative(value, municipality),
            }
        )
    return AreaStatisticsRead(
        area=_reference(selection.requested),
        statistics_area=_reference(selection.target),
        inherited_from_parent=selection.inherited,
        source=await _source(session),
        latest=latest,
    )


async def area_statistics(
    session: AsyncSession, selection: StatisticsSelection
) -> AreaStatisticsRead | None:
    version = await cache_version(session, "statistics")
    key = build_cache_key(
        "statistics:selection",
        {
            "requested": str(selection.requested.id),
            "target": str(selection.target.id),
            "municipality": str(selection.municipality.id),
        },
        version=version,
    )

    async def compute() -> dict | None:
        result = await _area_statistics_uncached(session, selection)
        return result.model_dump(mode="json") if result else None

    data, _status = await cache_service.get_or_compute(
        key,
        ttl=get_settings().statistics_cache_ttl,
        resource="statistics-selection",
        compute=compute,
    )
    return AreaStatisticsRead.model_validate(data) if data else None


async def _area_statistic_series_uncached(
    session: AsyncSession, selection: StatisticsSelection, metric_key: str
) -> AreaStatisticSeriesRead | None:
    context = await _mapping_context(session, selection)
    if context is None:
        return None
    metric = (
        await session.execute(
            text("""
              SELECT id,key,name,unit,category FROM statistical_metrics
              WHERE key=:key AND public=true
            """),
            {"key": metric_key},
        )
    ).mappings().first()
    if metric is None:
        return None
    rows = (
        await session.execute(
            text("""
              SELECT period_start,value_numeric,value_text
              FROM statistical_observations
              WHERE metric_id=:metric_id AND statistical_area_id=:area_id
              ORDER BY period_start
            """),
            {"metric_id": metric["id"], "area_id": context["statistics_id"]},
        )
    ).mappings().all()
    return AreaStatisticSeriesRead(
        area=_reference(selection.requested),
        statistics_area=_reference(selection.target),
        inherited_from_parent=selection.inherited,
        source=await _source(session),
        metric={key: str(metric[key]) for key in ("key", "name", "unit", "category")},
        series=[
            {
                "period": str(row["period_start"].year),
                "period_start": row["period_start"],
                "value": row["value_numeric"],
                "suppressed": row["value_text"] == "suppressed",
            }
            for row in rows
        ],
    )


async def area_statistic_series(
    session: AsyncSession, selection: StatisticsSelection, metric_key: str
) -> AreaStatisticSeriesRead | None:
    version = await cache_version(session, "statistics")
    key = build_cache_key(
        "statistics:selection-series",
        {
            "requested": str(selection.requested.id),
            "target": str(selection.target.id),
            "municipality": str(selection.municipality.id),
            "metric": metric_key,
        },
        version=version,
    )

    async def compute() -> dict | None:
        result = await _area_statistic_series_uncached(session, selection, metric_key)
        return result.model_dump(mode="json") if result else None

    data, _status = await cache_service.get_or_compute(
        key,
        ttl=get_settings().statistics_cache_ttl,
        resource="statistics-selection-series",
        compute=compute,
    )
    return AreaStatisticSeriesRead.model_validate(data) if data else None


async def statistics_source_status(session: AsyncSession) -> StatisticsDataSourceStatus:
    row = (
        await session.execute(
            text("""
              SELECT status,finished_at,checksum,error_message
              FROM statistical_import_runs WHERE source=:source
              ORDER BY started_at DESC LIMIT 1
            """),
            {"source": SOURCE},
        )
    ).mappings().first()
    success = await session.scalar(
        text("""
          SELECT max(finished_at) FROM statistical_import_runs
          WHERE source=:source AND status='SUCCESS'
        """),
        {"source": SOURCE},
    )
    source_updated = await session.scalar(
        text("SELECT max(source_updated_at) FROM statistical_datasets WHERE source=:source"),
        {"source": SOURCE},
    )
    records = int(
        await session.scalar(text("SELECT count(*) FROM statistical_observations")) or 0
    )
    return StatisticsDataSourceStatus(
        source="Stadt Flensburg – Zahlenspiegel",
        status=str(row["status"]) if row else "NOT_IMPORTED",
        last_success_at=success,
        source_updated_at=source_updated,
        records=records,
        checksum=row["checksum"] if row else None,
        error=row["error_message"] if row and row["status"] == "FAILED" else None,
    )
