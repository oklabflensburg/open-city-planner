"""HTTP consumer for the public API owned by the external Analysis Areas module."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field, TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.schemas.analytics import BenchmarkMetrics, IndustryCount
from app.schemas.external_links import ExternalLinks
from app.schemas.geojson import AreaGeometry


class AnalysisAreaRead(BaseModel):
    id: str
    slug: str
    name: str
    area_type: str
    parent_id: str | None = None
    parent_name: str | None = None
    parent_slug: str | None = None
    area_m2: float
    source: str
    source_osm_type: str | None = None
    source_osm_id: int | None = None
    source_admin_level: int | None = None
    source_place: str | None = None
    source_updated_at: datetime | None = None
    updated_at: datetime
    child_count: int = 0
    external_links: ExternalLinks = Field(default_factory=ExternalLinks)


class AnalysisAreaReference(BaseModel):
    id: str
    slug: str
    name: str
    area_type: str


class AnalysisAreaDetail(AnalysisAreaRead):
    parent: AnalysisAreaReference | None = None
    municipality: AnalysisAreaReference | None = None
    children: list[AnalysisAreaReference] = Field(default_factory=list)
    geometry: AreaGeometry
    centroid: tuple[float, float]
    bbox: tuple[float, float, float, float]


class AnalysisAreaPolygon(BaseModel):
    id: str
    slug: str
    name: str
    category: str
    floor: str | None = None
    address_display_name: str | None = None
    occupancy_status: str
    area_m2: float | None = None


class AnalysisAreaAnalytics(BaseModel):
    area: AnalysisAreaRead
    metrics: BenchmarkMetrics
    industry_distribution: list[IndustryCount]
    poi_count: int
    poi_categories: list[IndustryCount]
    retail_area_density_m2_per_km2: float | None = None


class MetricDifference(BaseModel):
    key: str
    area_value: float | int | None
    municipality_value: float | int | None
    difference: float | None
    unit: str = "absolute"


class AnalysisAreaComparison(BaseModel):
    area: AnalysisAreaRead
    municipality: AnalysisAreaRead
    area_metrics: BenchmarkMetrics
    municipality_metrics: BenchmarkMetrics
    differences: list[MetricDifference] = Field(default_factory=list)


def _url(path: str) -> str:
    return f"{get_settings().api_base_url.rstrip('/')}/api/v1{path}"


async def _get(path: str, *, params: dict[str, object] | None = None) -> object | None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        response = await client.get(_url(path), params=params)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def _filters(values: dict[str, Sequence[str]]) -> dict[str, object]:
    return {key: list(value) for key, value in values.items() if value}


async def list_areas(
    _session: AsyncSession,
    area_type: str | None = None,
    parent_id: uuid.UUID | None = None,
) -> list[AnalysisAreaRead]:
    params: dict[str, object] = {}
    if area_type is not None:
        params["area_type"] = area_type
    if parent_id is not None:
        params["parent_id"] = str(parent_id)
    payload = await _get("/analysis-areas", params=params)
    return TypeAdapter(list[AnalysisAreaRead]).validate_python(payload)


async def area_detail_by_slug(
    _session: AsyncSession, slug: str
) -> AnalysisAreaDetail | None:
    payload = await _get(f"/analysis-areas/by-slug/{quote(slug, safe='')}")
    return AnalysisAreaDetail.model_validate(payload) if payload is not None else None


async def area_uuid_by_slug(session: AsyncSession, slug: str) -> uuid.UUID | None:
    value = await area_detail_by_slug(session, slug)
    return uuid.UUID(value.id) if value is not None else None


async def areas_geojson(
    _session: AsyncSession, *, limit: int | None = None
) -> dict[str, object]:
    payload = await _get(
        "/analysis-areas/geojson",
        params={"limit": limit} if limit is not None else None,
    )
    return TypeAdapter(dict[str, object]).validate_python(payload)


async def area_polygons_by_slug(
    _session: AsyncSession, slug: str, limit: int = 8
) -> list[AnalysisAreaPolygon] | None:
    payload = await _get(
        f"/analysis-areas/by-slug/{quote(slug, safe='')}/polygons",
        params={"limit": limit},
    )
    if payload is None:
        return None
    return TypeAdapter(list[AnalysisAreaPolygon]).validate_python(payload)


async def area_analytics(
    _session: AsyncSession, area_id: uuid.UUID, **filters: Sequence[str]
) -> AnalysisAreaAnalytics | None:
    payload = await _get(
        f"/analysis-areas/{area_id}/analytics", params=_filters(filters)
    )
    return AnalysisAreaAnalytics.model_validate(payload) if payload is not None else None


async def area_comparison(
    _session: AsyncSession, area_id: uuid.UUID, **filters: Sequence[str]
) -> AnalysisAreaComparison | None:
    payload = await _get(
        f"/analysis-areas/{area_id}/comparison", params=_filters(filters)
    )
    return AnalysisAreaComparison.model_validate(payload) if payload is not None else None
