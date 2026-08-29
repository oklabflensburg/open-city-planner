"""Polygon-owned query helpers without Analysis Areas dependencies."""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_polygon import UserPolygon
from app.schemas.analytics import (
    BenchmarkMetrics,
    CompletenessMetric,
    DimensionCount,
    IndustryCount,
)
from app.schemas.polygon_filters import PolygonFilterParams
from app.services.polygon_filters import floor_group_expression, polygon_filter_clauses


def base_filters(
    floors: Sequence[str],
    area_sizes: Sequence[str],
    occupancy_statuses: Sequence[str] = (),
    business_structures: Sequence[str] = (),
    sources: Sequence[str] = (),
) -> list[object]:
    """Build public polygon filters without adding a foreign-domain scope."""

    return polygon_filter_clauses(
        PolygonFilterParams(
            floors=tuple(floors),
            area_sizes=tuple(area_sizes),
            occupancy_statuses=tuple(occupancy_statuses),
            business_structures=tuple(business_structures),
            sources=tuple(sources),
        )
    )


async def counts(
    session: AsyncSession,
    filters: Sequence[object],
) -> list[IndustryCount]:
    statement = (
        select(UserPolygon.category, func.count(UserPolygon.id))
        .where(*filters)
        .group_by(UserPolygon.category)
        .order_by(UserPolygon.category)
    )
    rows = (await session.execute(statement)).all()
    return [IndustryCount(category=category, count=int(count)) for category, count in rows]


async def benchmark_metrics(session: AsyncSession, filters: Sequence[object]) -> BenchmarkMetrics:
    area = func.ST_Area(func.ST_Transform(UserPolygon.geometry, 25832))
    area_size = UserPolygon.properties["size"].as_string()
    floor_group = floor_group_expression()
    statement = select(
        func.count(UserPolygon.id).label("polygon_count"),
        func.sum(area).label("total_area_m2"),
        func.avg(area).label("average_area_m2"),
        func.percentile_cont(0.5).within_group(area).label("median_area_m2"),
        func.sum(area).filter(UserPolygon.occupancy_status == "VACANT").label("vacant_area_m2"),
        func.sum(area)
        .filter(UserPolygon.occupancy_status != "UNKNOWN")
        .label("known_occupancy_area_m2"),
        func.count(UserPolygon.id)
        .filter(UserPolygon.occupancy_status != "UNKNOWN")
        .label("known_occupancy_count"),
        func.count(UserPolygon.id)
        .filter(UserPolygon.occupancy_status == "VACANT")
        .label("vacant_count"),
        func.count(UserPolygon.id)
        .filter(UserPolygon.business_structure != "UNKNOWN")
        .label("known_business_count"),
        func.count(UserPolygon.id)
        .filter(UserPolygon.business_structure == "CHAIN")
        .label("chain_count"),
        func.max(UserPolygon.updated_at).label("data_updated_at"),
        *[
            func.count(UserPolygon.id).filter(area_size == key).label(f"size_{key.lower()}_count")
            for key in ("S", "M", "L", "XL")
        ],
        *[
            func.count(UserPolygon.id)
            .filter(floor_group == key)
            .label(f"floor_{key.lower()}_count")
            for key in ("UG", "EG", "OG")
        ],
        func.count(UserPolygon.id)
        .filter(UserPolygon.occupancy_status == "OCCUPIED")
        .label("occupied_count"),
        func.count(UserPolygon.id)
        .filter(UserPolygon.business_structure == "INDEPENDENT")
        .label("independent_count"),
        func.count(UserPolygon.id)
        .filter(UserPolygon.category != "custom")
        .label("known_category_count"),
        func.count(UserPolygon.id).filter(floor_group.is_not(None)).label("known_floor_count"),
        func.count(UserPolygon.id).filter(area_size.is_not(None)).label("known_size_count"),
    ).where(*filters)
    row = (await session.execute(statement)).mappings().one()
    known_occupancy = int(row["known_occupancy_count"] or 0)
    known_business = int(row["known_business_count"] or 0)
    vacant = int(row["vacant_count"] or 0)
    chains = int(row["chain_count"] or 0)
    polygon_count = int(row["polygon_count"] or 0)
    vacant_area = float(row["vacant_area_m2"]) if row.get("vacant_area_m2") is not None else None
    known_occupancy_area = (
        float(row["known_occupancy_area_m2"])
        if row.get("known_occupancy_area_m2") is not None
        else None
    )

    def distribution(prefix: str, values: Sequence[tuple[str, str]]) -> list[DimensionCount]:
        return [
            DimensionCount(
                key=key,
                label=label,
                count=int(row.get(f"{prefix}_{key.lower()}_count") or 0),
            )
            for key, label in values
        ]

    def completeness(key: str, label: str, complete: int) -> CompletenessMetric:
        return CompletenessMetric(
            key=key,
            label=label,
            complete=complete,
            total=polygon_count,
            percent=round(complete / polygon_count * 100, 1) if polygon_count else None,
        )

    return BenchmarkMetrics(
        polygon_count=polygon_count,
        occupied_count=known_occupancy - vacant,
        vacant_count=vacant,
        chain_count=chains,
        independent_count=known_business - chains,
        total_area_m2=(float(row["total_area_m2"]) if row["total_area_m2"] is not None else None),
        average_area_m2=(
            float(row["average_area_m2"]) if row["average_area_m2"] is not None else None
        ),
        median_area_m2=(
            float(row["median_area_m2"]) if row.get("median_area_m2") is not None else None
        ),
        vacant_area_m2=vacant_area,
        vacancy_area_rate=(
            round(vacant_area / known_occupancy_area * 100, 2)
            if vacant_area is not None and known_occupancy_area
            else None
        ),
        vacancy_rate=(round(vacant / known_occupancy * 100, 2) if known_occupancy else None),
        chain_store_rate=(round(chains / known_business * 100, 2) if known_business else None),
        known_occupancy_count=known_occupancy,
        known_business_structure_count=known_business,
        data_updated_at=row.get("data_updated_at"),
        size_distribution=[
            *distribution("size", (("S", "S"), ("M", "M"), ("L", "L"), ("XL", "XL"))),
            DimensionCount(
                key="UNKNOWN",
                label="Ohne Angabe",
                count=polygon_count - int(row.get("known_size_count") or 0),
            ),
        ],
        floor_distribution=[
            *distribution("floor", (("UG", "UG"), ("EG", "EG"), ("OG", "OG"))),
            DimensionCount(
                key="UNKNOWN",
                label="Ohne Angabe",
                count=polygon_count - int(row.get("known_floor_count") or 0),
            ),
        ],
        status_distribution=[
            DimensionCount(
                key="OCCUPIED",
                label="Belegt",
                count=int(row.get("occupied_count") or (known_occupancy - vacant)),
            ),
            DimensionCount(key="VACANT", label="Leerstehend", count=vacant),
            DimensionCount(
                key="UNKNOWN",
                label="Ohne Angabe",
                count=polygon_count - known_occupancy,
            ),
        ],
        business_structure_distribution=[
            DimensionCount(key="CHAIN", label="Filiale", count=chains),
            DimensionCount(
                key="INDEPENDENT",
                label="Inhabergeführt",
                count=int(row.get("independent_count") or (known_business - chains)),
            ),
            DimensionCount(
                key="UNKNOWN",
                label="Ohne Angabe",
                count=polygon_count - known_business,
            ),
        ],
        data_completeness=[
            completeness("category", "Branche", int(row.get("known_category_count") or 0)),
            completeness("area_size", "Größenklasse", int(row.get("known_size_count") or 0)),
            completeness("floor", "Etage", int(row.get("known_floor_count") or 0)),
            completeness("occupancy_status", "Belegungsstatus", known_occupancy),
            completeness("business_structure", "Betriebsform", known_business),
        ],
    )
