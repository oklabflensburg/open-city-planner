from datetime import datetime

from pydantic import BaseModel, Field


class DimensionCount(BaseModel):
    key: str
    label: str
    count: int


class CompletenessMetric(BaseModel):
    key: str
    label: str
    complete: int
    total: int
    percent: float | None = None


class IndustryCount(BaseModel):
    category: str
    count: int


class BenchmarkMetrics(BaseModel):
    """Aggregate metrics over generic Host polygons."""

    polygon_count: int
    occupied_count: int
    vacant_count: int
    chain_count: int
    independent_count: int
    total_area_m2: float | None = None
    average_area_m2: float | None = None
    median_area_m2: float | None = None
    vacant_area_m2: float | None = None
    vacancy_area_rate: float | None = None
    vacancy_rate: float | None = None
    chain_store_rate: float | None = None
    known_occupancy_count: int
    known_business_structure_count: int
    data_updated_at: datetime | None = None
    size_distribution: list[DimensionCount] = Field(default_factory=list)
    floor_distribution: list[DimensionCount] = Field(default_factory=list)
    status_distribution: list[DimensionCount] = Field(default_factory=list)
    business_structure_distribution: list[DimensionCount] = Field(default_factory=list)
    data_completeness: list[CompletenessMetric] = Field(default_factory=list)
