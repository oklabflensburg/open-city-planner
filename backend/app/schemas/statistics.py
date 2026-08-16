from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class StatisticsAreaReference(BaseModel):
    id: UUID
    slug: str
    name: str
    area_type: str


class StatisticsSource(BaseModel):
    name: str
    url: str
    license: str
    source_updated_at: datetime | None
    last_import_at: datetime | None


class AreaStatisticValue(BaseModel):
    key: str
    name: str
    category: str
    value: Decimal | None
    unit: str
    period: str
    period_start: date
    area_level: str
    is_calculated: bool
    municipality_value: Decimal | None = None
    difference: Decimal | None = None
    relative_difference: Decimal | None = None


class AreaStatisticsRead(BaseModel):
    area: StatisticsAreaReference
    statistics_area: StatisticsAreaReference
    inherited_from_parent: bool
    source: StatisticsSource | None
    latest: list[AreaStatisticValue] = Field(default_factory=list)


class StatisticSeriesPoint(BaseModel):
    period: str
    period_start: date
    value: Decimal | None
    suppressed: bool


class AreaStatisticSeriesRead(BaseModel):
    area: StatisticsAreaReference
    statistics_area: StatisticsAreaReference
    inherited_from_parent: bool
    source: StatisticsSource | None
    metric: dict[str, str]
    series: list[StatisticSeriesPoint] = Field(default_factory=list)


class StatisticsDataSourceStatus(BaseModel):
    source: str
    status: str
    last_success_at: datetime | None
    source_updated_at: datetime | None
    records: int
    checksum: str | None
    error: str | None = None
