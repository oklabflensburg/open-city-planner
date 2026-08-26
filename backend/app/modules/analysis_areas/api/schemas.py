"""Stable public API schemas owned by the Analysis Areas module."""

from datetime import datetime

from pydantic import BaseModel, Field

from ..integrations.legacy import AreaGeometry, BenchmarkMetrics, ExternalLinks, IndustryCount

AnalysisAreaExternalLinks = ExternalLinks


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
    external_links: AnalysisAreaExternalLinks = Field(default_factory=AnalysisAreaExternalLinks)


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


class AnalysisAreaSitemapEntry(BaseModel):
    slug: str
    updated_at: datetime


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
