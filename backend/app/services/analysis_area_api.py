import uuid
from collections.abc import Sequence

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis_area import AnalysisArea, PolygonAnalysisArea
from app.models.user_polygon import UserPolygon
from app.schemas.analysis_area import (
    AnalysisAreaAnalytics,
    AnalysisAreaComparison,
    AnalysisAreaRead,
    MetricDifference,
)
from app.schemas.analytics import IndustryCount
from app.services.analytics import _base_filters, _benchmark_metrics, _counts

AREA_SELECT = text("""
SELECT area.uuid::text AS id, area.slug, area.name, area.area_type, parent.uuid::text AS parent_id,
       parent.name AS parent_name, area.area_m2, area.source, area.source_osm_type, area.source_osm_id,
       area.source_admin_level, area.source_place, area.source_updated_at,
       (SELECT count(*) FROM analysis_areas child WHERE child.parent_id=area.id) AS child_count
FROM analysis_areas area LEFT JOIN analysis_areas parent ON parent.id=area.parent_id
""")


def _read(row: dict) -> AnalysisAreaRead:
    return AnalysisAreaRead(**row)


async def list_areas(session: AsyncSession, area_type: str | None = None, parent_id: uuid.UUID | None = None) -> list[AnalysisAreaRead]:
    sql = AREA_SELECT.text + " WHERE (CAST(:area_type AS varchar) IS NULL OR area.area_type=CAST(:area_type AS varchar)) AND (CAST(:parent_id AS uuid) IS NULL OR parent.uuid=CAST(:parent_id AS uuid)) ORDER BY CASE area.area_type WHEN 'MUNICIPALITY' THEN 1 WHEN 'DISTRICT' THEN 2 ELSE 3 END, area.name"
    rows = (await session.execute(text(sql), {"area_type": area_type, "parent_id": parent_id})).mappings().all()
    return [_read(dict(row)) for row in rows]


async def area_detail(session: AsyncSession, area_id: uuid.UUID) -> AnalysisAreaRead | None:
    row = (await session.execute(text(AREA_SELECT.text + " WHERE area.uuid=:area_id"), {"area_id": area_id})).mappings().first()
    return _read(dict(row)) if row else None


async def areas_geojson(session: AsyncSession) -> dict:
    rows = (await session.execute(text("""
      SELECT uuid::text AS id, slug, name, area_type, parent_id, area_m2, source,
             source_osm_type, source_osm_id, source_admin_level,
             ST_AsGeoJSON(geometry,6)::json AS geometry
      FROM analysis_areas ORDER BY CASE area_type WHEN 'MUNICIPALITY' THEN 1 WHEN 'DISTRICT' THEN 2 ELSE 3 END,name
    """))).mappings().all()
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": row["id"], "geometry": row["geometry"],
         "properties": {key: value for key, value in row.items() if key != "geometry"}}
        for row in rows
    ]}


def _filters(area_db_id: int, *, categories: Sequence[str], floors: Sequence[str], area_sizes: Sequence[str], occupancy_statuses: Sequence[str], business_structures: Sequence[str]) -> list[object]:
    result = _base_filters(floors, area_sizes, occupancy_statuses, business_structures)
    result.append(UserPolygon.id.in_(select(PolygonAnalysisArea.polygon_id).where(PolygonAnalysisArea.analysis_area_id == area_db_id)))
    if categories:
        result.append(UserPolygon.category.in_(categories))
    return result


async def _area_row(session: AsyncSession, area_id: uuid.UUID) -> tuple[AnalysisArea, AnalysisAreaRead] | None:
    model = await session.scalar(select(AnalysisArea).where(AnalysisArea.uuid == area_id))
    detail = await area_detail(session, area_id)
    return (model, detail) if model and detail else None


async def area_analytics(session: AsyncSession, area_id: uuid.UUID, **kwargs) -> AnalysisAreaAnalytics | None:
    found = await _area_row(session, area_id)
    if not found:
        return None
    area, detail = found
    selected_filters = _filters(area.id, **kwargs)
    metrics = await _benchmark_metrics(session, selected_filters)
    distribution = await _counts(session, selected_filters)
    poi_rows = (await session.execute(text("""
      SELECT coalesce(tags->>'shop',tags->>'amenity',tags->>'tourism',tags->>'leisure','other') AS category, count(*) AS count
      FROM osm_features WHERE ST_Covers((SELECT geometry FROM analysis_areas WHERE id=:id), ST_PointOnSurface(geometry))
        AND (tags ? 'shop' OR tags ? 'amenity' OR tags ? 'tourism' OR tags ? 'leisure')
      GROUP BY 1 ORDER BY count(*) DESC, 1
    """), {"id": area.id})).all()
    poi_categories = [IndustryCount(category=str(category), count=int(count)) for category, count in poi_rows]
    density = metrics.total_area_m2 / (area.area_m2 / 1_000_000) if metrics.total_area_m2 is not None and area.area_m2 else None
    return AnalysisAreaAnalytics(area=detail, metrics=metrics, industry_distribution=distribution,
                                 poi_count=sum(item.count for item in poi_categories), poi_categories=poi_categories,
                                 retail_area_density_m2_per_km2=round(density, 2) if density is not None else None)


async def area_comparison(session: AsyncSession, area_id: uuid.UUID, **kwargs) -> AnalysisAreaComparison | None:
    found = await _area_row(session, area_id)
    if not found:
        return None
    area, detail = found
    municipality = area if area.area_type == "MUNICIPALITY" else await session.scalar(
        select(AnalysisArea).where(AnalysisArea.area_type == "MUNICIPALITY", func.ST_Covers(AnalysisArea.geometry, area.centroid)).limit(1)
    )
    if municipality is None:
        return None
    municipality_detail = await area_detail(session, municipality.uuid)
    if municipality_detail is None:
        return None
    area_metrics = await _benchmark_metrics(session, _filters(area.id, **kwargs))
    city_metrics = await _benchmark_metrics(session, _filters(municipality.id, **kwargs))
    differences = []
    for key, unit in (("polygon_count", "absolute"), ("total_area_m2", "m²"), ("average_area_m2", "m²"),
                      ("vacancy_rate", "percentage_points"), ("chain_store_rate", "percentage_points")):
        selected = getattr(area_metrics, key)
        city = getattr(city_metrics, key)
        difference = round(float(selected) - float(city), 2) if selected is not None and city is not None else None
        differences.append(MetricDifference(key=key, area_value=selected, municipality_value=city, difference=difference, unit=unit))
    return AnalysisAreaComparison(area=detail, municipality=municipality_detail, area_metrics=area_metrics,
                                  municipality_metrics=city_metrics, differences=differences)
