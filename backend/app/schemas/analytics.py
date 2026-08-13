from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

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
    updated_at: datetime | None = None


class CityMetricsVerwaltungRead(CityMetricsPublicRead):
    source: str | None = None
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
            raise ValueError("At least one field must be provided")
        return self


class AnalyticsFastFacts(CityMetricsPublicRead):
    shops: int


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
    prime_rents: PrimeRentData
