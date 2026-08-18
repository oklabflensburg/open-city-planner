from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator, model_validator

JsonDecimal = Annotated[
    Decimal,
    PlainSerializer(lambda value: float(value), return_type=float, when_used="json"),
]


class CityMetricsPublicRead(BaseModel):
    vacancy_rate: JsonDecimal | None = None
    chain_store_rate: JsonDecimal | None = None
    centrality_index: JsonDecimal | None = None
    purchasing_power_index: JsonDecimal | None = None
    reference_date: date | None = None
    source: str | None = None
    updated_at: datetime | None = None


class CityMetricsVerwaltungRead(CityMetricsPublicRead):
    notes: str | None = None
    updated_by_user_id: str | None = None


class CityMetricsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vacancy_rate: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    chain_store_rate: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    centrality_index: Decimal | None = Field(default=None, ge=0, max_digits=8, decimal_places=2)
    purchasing_power_index: Decimal | None = Field(default=None, ge=0, max_digits=8, decimal_places=2)
    reference_date: date | None = None
    source: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=10000)

    @field_validator("source", "notes")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def require_changed_field(self) -> "CityMetricsUpdate":
        if not self.model_fields_set:
            raise ValueError("Mindestens ein Feld muss angegeben werden")
        return self


class AnalyticsFastFacts(CityMetricsPublicRead):
    shops: int
    polygon_count: int = 0
    total_area_m2: float | None = None
    average_area_m2: float | None = None
    median_area_m2: float | None = None
    vacant_area_m2: float | None = None
    vacancy_area_rate: float | None = None
    calculated_vacancy_rate: float | None = None
    calculated_chain_store_rate: float | None = None
    known_occupancy_count: int = 0
    known_business_structure_count: int = 0
    data_updated_at: datetime | None = None


class BenchmarkMetrics(BaseModel):
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
    size_distribution: list["DimensionCount"] = Field(default_factory=list)
    floor_distribution: list["DimensionCount"] = Field(default_factory=list)
    status_distribution: list["DimensionCount"] = Field(default_factory=list)
    business_structure_distribution: list["DimensionCount"] = Field(default_factory=list)
    data_completeness: list["CompletenessMetric"] = Field(default_factory=list)


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


class MarketBenchmark(BaseModel):
    key: str
    label: str
    metrics: BenchmarkMetrics


class MarketBenchmarkResult(BaseModel):
    items: list[MarketBenchmark]
    context_label: str
    calculation: str = "CALCULATED"
    source: str = "Erfasste Stadtplaner-Flächen"


class AreaCompareFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categories: list[Literal[
        "warehouse", "fashion", "food", "electronics", "furniture", "garden",
        "other", "gastronomy", "services", "otherAreas", "__none__", "NONE",
    ]] = Field(default_factory=list)
    floors: list[Literal["UG", "EG", "OG", "NONE"]] = Field(default_factory=list)
    area_sizes: list[Literal["S", "M", "L", "XL", "NONE"]] = Field(default_factory=list)
    occupancy_statuses: list[Literal["OCCUPIED", "VACANT", "UNKNOWN", "NONE"]] = Field(default_factory=list)
    business_structures: list[Literal["CHAIN", "INDEPENDENT", "UNKNOWN", "NONE"]] = Field(default_factory=list)
    sources: list[Literal["STADTPLANNER", "OSM", "NONE"]] = Field(default_factory=list)


class AreaCompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    area_slugs: list[str] = Field(min_length=1, max_length=4)
    include_municipality_benchmark: bool = True
    filters: AreaCompareFilters = Field(default_factory=AreaCompareFilters)

    @field_validator("area_slugs")
    @classmethod
    def unique_normalized_slugs(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().lower() for value in values if value.strip()]
        if not normalized:
            raise ValueError("Mindestens ein Gebietsslug ist erforderlich")
        return list(dict.fromkeys(normalized))


class AreaCompareMetrics(BaseModel):
    polygon_count: int = 0
    occupied_count: int = 0
    vacant_count: int = 0
    chain_count: int = 0
    independent_count: int = 0
    total_area_m2: float | None = None
    average_area_m2: float | None = None
    median_area_m2: float | None = None
    vacancy_rate: float | None = None
    chain_store_rate: float | None = None
    known_occupancy_count: int = 0
    known_business_structure_count: int = 0
    data_updated_at: datetime | None = None
    locations_per_km2: float | None = None
    retail_area_m2_per_km2: float | None = None


class AreaCompareItem(BaseModel):
    id: str
    slug: str
    name: str
    area_type: Literal["MUNICIPALITY", "DISTRICT", "QUARTER"]
    parent_name: str | None = None
    area_m2: float
    metrics: AreaCompareMetrics


class AreaCompareResult(BaseModel):
    areas: list[AreaCompareItem]
    benchmark: AreaCompareItem | None = None
    ignored_slugs: list[str] = Field(default_factory=list)
    calculation: str = "CALCULATED"
    source: str = "Erfasste Stadtplaner-Flächen"


class PoiCount(BaseModel):
    category: str
    label: str
    count: int


class NearestPoi(BaseModel):
    category: str
    label: str
    name: str | None = None
    distance_m: float


class LocationAnalysis(BaseModel):
    polygon_slug: str
    radius_m: int
    poi_counts: list[PoiCount]
    nearest_public_transport: NearestPoi | None = None
    source: str = "OpenStreetMap"
    reference_date: datetime | None = None


class ComparablePolygon(BaseModel):
    slug: str
    title: str
    distance_m: float
    area_m2: float
    category: str
    floor: str | None = None
    similarity_score: float


class ComparableResult(BaseModel):
    polygon_slug: str
    items: list[ComparablePolygon]
    calculation: str = "CALCULATED"


class IndustryCount(BaseModel):
    category: str
    count: int


class PrimeRentRow(BaseModel):
    location: str
    s: float | None = None
    m: float | None = None
    l: float | None = None
    xl: float | None = None


class PrimeRentData(BaseModel):
    unit: str = "EUR_PER_SQM"
    period: str | None = None
    rows: list[PrimeRentRow] = Field(default_factory=list)


class AnalyticsOverview(BaseModel):
    fast_facts: AnalyticsFastFacts
    industry_distribution: list[IndustryCount]
    category_counts: list[IndustryCount]
    size_distribution: list[DimensionCount] = Field(default_factory=list)
    floor_distribution: list[DimensionCount] = Field(default_factory=list)
    status_distribution: list[DimensionCount] = Field(default_factory=list)
    business_structure_distribution: list[DimensionCount] = Field(default_factory=list)
    data_completeness: list[CompletenessMetric] = Field(default_factory=list)
    prime_rents: PrimeRentData
