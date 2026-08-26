"""Typisierte und ausschließlich namespacete Einstellungen des Referenzmoduls."""

from pydantic import BaseModel, ConfigDict, Field


class ReferenceSettings(BaseModel):
    max_items: int = Field(default=100, ge=1, le=500, json_schema_extra={"public": True})
    job_interval_seconds: int = Field(default=3600, ge=60, le=86400)

    model_config = ConfigDict(frozen=True)
