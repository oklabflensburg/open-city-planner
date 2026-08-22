import uuid
from collections.abc import Sequence
from urllib.parse import quote

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.keys import build_cache_key
from app.cache.service import cache_service
from app.core.config import get_settings
from app.models.analysis_area import AnalysisArea, PolygonAnalysisArea
from app.models.user_polygon import UserPolygon
from app.schemas.analysis_area import (
    AnalysisAreaAnalytics,
    AnalysisAreaComparison,
    AnalysisAreaDetail,
    AnalysisAreaExternalLinks,
    AnalysisAreaPolygon,
    AnalysisAreaRead,
    AnalysisAreaReference,
    AnalysisAreaSitemapEntry,
    MetricDifference,
)
from app.schemas.analytics import IndustryCount
from app.schemas.external_links import WikidataExternalLink, WikipediaExternalLink
from app.services.analytics import _base_filters, _benchmark_metrics, _counts
from app.services.cache_versions import cache_version
from app.services.poi_categories import AREA_POI_CATEGORY_SQL

AREA_SELECT = text("""
SELECT area.uuid::text AS id, area.slug, area.name, area.area_type, parent.uuid::text AS parent_id,
       parent.name AS parent_name, parent.slug AS parent_slug, area.area_m2, area.source, area.source_osm_type, area.source_osm_id,
       area.source_admin_level, area.source_place, area.source_updated_at,
       CASE WHEN area.wikidata_match_status IN ('VERIFIED','AUTO_MATCHED') THEN area.wikidata_id END AS public_wikidata_id,
       CASE WHEN area.wikidata_match_status IN ('VERIFIED','AUTO_MATCHED') THEN area.wikipedia_title END AS public_wikipedia_title,
       area.updated_at,
       (SELECT count(*) FROM analysis_areas child WHERE child.parent_id=area.id) AS child_count
FROM analysis_areas area LEFT JOIN analysis_areas parent ON parent.id=area.parent_id
""")


POI_TAG_PREDICATE_SQL = """
osm.tags ? 'shop'
OR osm.tags ? 'amenity'
OR osm.tags ? 'tourism'
OR osm.tags ? 'leisure'
"""

# ST_PointOnSurface(osm.geometry) ist kein Ausdruck des GiST-Indexes auf geometry.
# Der Bounding-Box-Operator begrenzt deshalb zuerst indexierbar die Kandidatenmenge.
AREA_POI_ANALYTICS_SQL = text(f"""
WITH target AS (
  SELECT geometry
  FROM analysis_areas
  WHERE id = :id
)
SELECT
  {AREA_POI_CATEGORY_SQL} AS category,
  count(*) AS count
FROM osm_features osm
CROSS JOIN target
WHERE osm.geometry && target.geometry
  AND ST_Covers(target.geometry, ST_PointOnSurface(osm.geometry))
  AND ({POI_TAG_PREDICATE_SQL})
GROUP BY 1
ORDER BY count(*) DESC, 1
""")


async def _area_poi_categories(session: AsyncSession, area_db_id: int) -> list[IndustryCount]:
    rows = (await session.execute(AREA_POI_ANALYTICS_SQL, {"id": area_db_id})).all()
    return [IndustryCount(category=str(category), count=int(count)) for category, count in rows]


def _external_links(values: dict) -> AnalysisAreaExternalLinks:
    qid = values.pop("public_wikidata_id", None)
    title = values.pop("public_wikipedia_title", None)
    return AnalysisAreaExternalLinks(
        wikidata=WikidataExternalLink(
            id=qid, url=f"https://www.wikidata.org/wiki/{qid}"
        ) if qid else None,
        wikipedia=WikipediaExternalLink(
            title=title,
            url=f"https://de.wikipedia.org/wiki/{quote(title.replace(' ', '_'), safe='()_-')}"
        ) if title else None,
    )


def _read(row: dict) -> AnalysisAreaRead:
    values = dict(row)
    return AnalysisAreaRead(**values, external_links=_external_links(values))


async def _list_areas_uncached(session: AsyncSession, area_type: str | None = None, parent_id: uuid.UUID | None = None) -> list[AnalysisAreaRead]:
    sql = AREA_SELECT.text + " WHERE (CAST(:area_type AS varchar) IS NULL OR area.area_type=CAST(:area_type AS varchar)) AND (CAST(:parent_id AS uuid) IS NULL OR parent.uuid=CAST(:parent_id AS uuid)) ORDER BY CASE area.area_type WHEN 'MUNICIPALITY' THEN 1 WHEN 'DISTRICT' THEN 2 ELSE 3 END, area.name"
    rows = (await session.execute(text(sql), {"area_type": area_type, "parent_id": parent_id})).mappings().all()
    return [_read(dict(row)) for row in rows]


async def _area_detail_uncached(session: AsyncSession, area_id: uuid.UUID) -> AnalysisAreaRead | None:
    row = (await session.execute(text(AREA_SELECT.text + " WHERE area.uuid=:area_id"), {"area_id": area_id})).mappings().first()
    return _read(dict(row)) if row else None


async def _area_detail_by_slug_uncached(session: AsyncSession, slug: str) -> AnalysisAreaDetail | None:
    row = (await session.execute(text("""
      SELECT area.uuid::text AS id, area.slug, area.name, area.area_type,
        parent.uuid::text AS parent_id, parent.name AS parent_name, parent.slug AS parent_slug,
        parent.area_type AS parent_type, municipality.uuid::text AS municipality_id,
        municipality.slug AS municipality_slug, municipality.name AS municipality_name,
        area.area_m2, area.source, area.source_osm_type, area.source_osm_id,
        area.source_admin_level, area.source_place, area.source_updated_at, area.updated_at,
        CASE WHEN area.wikidata_match_status IN ('VERIFIED','AUTO_MATCHED') THEN area.wikidata_id END AS public_wikidata_id,
        CASE WHEN area.wikidata_match_status IN ('VERIFIED','AUTO_MATCHED') THEN area.wikipedia_title END AS public_wikipedia_title,
        (SELECT count(*) FROM analysis_areas child WHERE child.parent_id=area.id) AS child_count,
        ST_AsGeoJSON(area.geometry,6)::json AS geometry,
        ARRAY[ST_X(area.centroid),ST_Y(area.centroid)] AS centroid,
        ARRAY[ST_XMin(Box2D(area.geometry)),ST_YMin(Box2D(area.geometry)),
              ST_XMax(Box2D(area.geometry)),ST_YMax(Box2D(area.geometry))] AS bbox
      FROM analysis_areas area LEFT JOIN analysis_areas parent ON parent.id=area.parent_id
      LEFT JOIN analysis_areas municipality ON municipality.id=CASE
        WHEN area.area_type='DISTRICT' THEN parent.id
        WHEN area.area_type='QUARTER' THEN parent.parent_id
        ELSE NULL END
      WHERE area.slug=:slug AND NOT ST_IsEmpty(area.geometry)
    """), {"slug": slug})).mappings().first()
    if not row:
        return None
    children = (await session.execute(text("""
      SELECT uuid::text AS id, slug, name, area_type FROM analysis_areas
      WHERE parent_id=(SELECT id FROM analysis_areas WHERE slug=:slug)
        AND NOT ST_IsEmpty(geometry)
      ORDER BY CASE area_type WHEN 'DISTRICT' THEN 1 ELSE 2 END,name
    """), {"slug": slug})).mappings().all()
    values = dict(row)
    parent_type = values.pop("parent_type")
    municipality_id = values.pop("municipality_id")
    municipality_slug = values.pop("municipality_slug")
    municipality_name = values.pop("municipality_name")
    external_links = _external_links(values)
    parent = AnalysisAreaReference(
        id=values["parent_id"], slug=values["parent_slug"],
        name=values["parent_name"], area_type=parent_type,
    ) if values["parent_id"] else None
    municipality = AnalysisAreaReference(
        id=municipality_id, slug=municipality_slug,
        name=municipality_name, area_type="MUNICIPALITY",
    ) if municipality_id else None
    return AnalysisAreaDetail(
        **values, parent=parent, municipality=municipality, external_links=external_links,
        children=[AnalysisAreaReference(**dict(child)) for child in children],
    )


async def _areas_geojson_uncached(session: AsyncSession) -> dict:
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


def _filters(area_db_id: int, *, categories: Sequence[str], floors: Sequence[str], area_sizes: Sequence[str], occupancy_statuses: Sequence[str], business_structures: Sequence[str], sources: Sequence[str]) -> list[object]:
    result = _base_filters(floors, area_sizes, occupancy_statuses, business_structures, sources)
    result.append(UserPolygon.id.in_(select(PolygonAnalysisArea.polygon_id).where(PolygonAnalysisArea.analysis_area_id == area_db_id)))
    if categories:
        result.append(UserPolygon.category.in_(categories))
    return result


async def _area_row(session: AsyncSession, area_id: uuid.UUID) -> tuple[AnalysisArea, AnalysisAreaRead] | None:
    model = await session.scalar(select(AnalysisArea).where(AnalysisArea.uuid == area_id))
    detail = await area_detail(session, area_id)
    return (model, detail) if model and detail else None


async def _area_analytics_uncached(session: AsyncSession, area_id: uuid.UUID, **kwargs) -> AnalysisAreaAnalytics | None:
    found = await _area_row(session, area_id)
    if not found:
        return None
    area, detail = found
    selected_filters = _filters(area.id, **kwargs)
    metrics = await _benchmark_metrics(session, selected_filters)
    distribution = await _counts(session, selected_filters)
    poi_categories: list[IndustryCount] = []
    if not kwargs["sources"] or "OSM" in kwargs["sources"]:
        poi_categories = await _area_poi_categories(session, area.id)
    density = metrics.total_area_m2 / (area.area_m2 / 1_000_000) if metrics.total_area_m2 is not None and area.area_m2 else None
    return AnalysisAreaAnalytics(area=detail, metrics=metrics, industry_distribution=distribution,
                                 poi_count=sum(item.count for item in poi_categories), poi_categories=poi_categories,
                                 retail_area_density_m2_per_km2=round(density, 2) if density is not None else None)


async def _area_comparison_uncached(session: AsyncSession, area_id: uuid.UUID, **kwargs) -> AnalysisAreaComparison | None:
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


async def list_areas(
    session: AsyncSession,
    area_type: str | None = None,
    parent_id: uuid.UUID | None = None,
) -> list[AnalysisAreaRead]:
    version = await cache_version(session, "analysis-areas")
    key = build_cache_key(
        "analysis-area:list", {"area_type": area_type, "parent_id": parent_id}, version=version
    )

    async def compute() -> list[dict]:
        rows = await _list_areas_uncached(session, area_type, parent_id)
        return [row.model_dump(mode="json") for row in rows]

    data, _status = await cache_service.get_or_compute(
        key, ttl=get_settings().analysis_area_cache_ttl, resource="analysis-area-list", compute=compute
    )
    return [AnalysisAreaRead.model_validate(row) for row in data]


async def area_detail(session: AsyncSession, area_id: uuid.UUID) -> AnalysisAreaRead | None:
    version = await cache_version(session, "analysis-areas")
    key = build_cache_key("analysis-area:detail", {"area_id": area_id}, version=version)

    async def compute() -> dict | None:
        result = await _area_detail_uncached(session, area_id)
        return result.model_dump(mode="json") if result else None

    data, _status = await cache_service.get_or_compute(
        key, ttl=get_settings().analysis_area_cache_ttl, resource="analysis-area-detail", compute=compute
    )
    return AnalysisAreaRead.model_validate(data) if data else None


async def area_detail_by_slug(session: AsyncSession, slug: str) -> AnalysisAreaDetail | None:
    version = await cache_version(session, "analysis-areas")
    key = build_cache_key("analysis-area:detail-by-slug", {"slug": slug}, version=version)

    async def compute() -> dict | None:
        result = await _area_detail_by_slug_uncached(session, slug)
        return result.model_dump(mode="json") if result else None

    data, _status = await cache_service.get_or_compute(
        key, ttl=get_settings().analysis_area_cache_ttl,
        resource="analysis-area-detail-by-slug", compute=compute,
    )
    return AnalysisAreaDetail.model_validate(data) if data else None


async def area_polygons_by_slug(session: AsyncSession, slug: str, limit: int = 8) -> list[AnalysisAreaPolygon] | None:
    area_version = await cache_version(session, "analysis-areas")
    analytics_version = await cache_version(session, "analytics")
    key = build_cache_key(
        "analysis-area:polygons-by-slug", {"slug": slug, "limit": limit},
        version=f"{area_version}:{analytics_version}",
    )

    async def compute() -> list[dict] | None:
        area_id = await session.scalar(select(AnalysisArea.id).where(AnalysisArea.slug == slug))
        if area_id is None:
            return None
        rows = (await session.execute(text("""
          SELECT polygon.uuid::text AS id, polygon.slug, polygon.name, polygon.category, polygon.floor,
            polygon.address_display_name, coalesce(polygon.occupancy_status,'UNKNOWN') AS occupancy_status,
            ST_Area(ST_Transform(polygon.geometry,25832)) AS area_m2
          FROM polygon_analysis_areas assignment
          JOIN user_polygons polygon ON polygon.id=assignment.polygon_id
          WHERE assignment.analysis_area_id=:area_id
          ORDER BY polygon.updated_at DESC,polygon.id DESC LIMIT :limit
        """), {"area_id": area_id, "limit": limit})).mappings().all()
        return [AnalysisAreaPolygon(**dict(row)).model_dump(mode="json") for row in rows]

    data, _status = await cache_service.get_or_compute(
        key, ttl=get_settings().analytics_cache_ttl,
        resource="analysis-area-polygons-by-slug", compute=compute,
    )
    return [AnalysisAreaPolygon.model_validate(row) for row in data] if data is not None else None


async def analysis_area_sitemap_entries(session: AsyncSession) -> list[AnalysisAreaSitemapEntry]:
    rows = (await session.execute(text("""
      SELECT slug,updated_at FROM analysis_areas
      WHERE geometry IS NOT NULL AND NOT ST_IsEmpty(geometry)
      ORDER BY slug
    """))).mappings().all()
    return [AnalysisAreaSitemapEntry(**dict(row)) for row in rows]


async def area_uuid_by_slug(session: AsyncSession, slug: str) -> uuid.UUID | None:
    return await session.scalar(select(AnalysisArea.uuid).where(AnalysisArea.slug == slug))


async def areas_geojson(session: AsyncSession) -> dict:
    version = await cache_version(session, "analysis-areas")
    key = build_cache_key("analysis-area:geojson", {}, version=version)
    data, _status = await cache_service.get_or_compute(
        key,
        ttl=get_settings().analysis_area_cache_ttl,
        resource="analysis-area-geojson",
        compute=lambda: _areas_geojson_uncached(session),
    )
    return data


async def area_analytics(
    session: AsyncSession, area_id: uuid.UUID, **kwargs
) -> AnalysisAreaAnalytics | None:
    version = await cache_version(session, "analytics")
    key = build_cache_key(
        "analysis-area:analytics", {"area_id": area_id, **kwargs}, version=version
    )

    async def compute() -> dict | None:
        result = await _area_analytics_uncached(session, area_id, **kwargs)
        return result.model_dump(mode="json") if result else None

    data, _status = await cache_service.get_or_compute(
        key, ttl=get_settings().analytics_cache_ttl, resource="analysis-area-analytics", compute=compute
    )
    return AnalysisAreaAnalytics.model_validate(data) if data else None


async def area_comparison(
    session: AsyncSession, area_id: uuid.UUID, **kwargs
) -> AnalysisAreaComparison | None:
    version = await cache_version(session, "analytics")
    key = build_cache_key(
        "analysis-area:comparison", {"area_id": area_id, **kwargs}, version=version
    )

    async def compute() -> dict | None:
        result = await _area_comparison_uncached(session, area_id, **kwargs)
        return result.model_dump(mode="json") if result else None

    data, _status = await cache_service.get_or_compute(
        key, ttl=get_settings().analytics_cache_ttl, resource="analysis-area-comparison", compute=compute
    )
    return AnalysisAreaComparison.model_validate(data) if data else None
