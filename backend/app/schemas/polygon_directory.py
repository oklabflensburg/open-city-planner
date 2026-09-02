from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PolygonDirectoryItem(BaseModel):
    slug: str
    name: str
    category: str
    floor: str | None = None
    address_display_name: str | None = None
    occupancy_status: Literal["OCCUPIED", "VACANT", "UNKNOWN"] = "UNKNOWN"
    business_structure: Literal["CHAIN", "INDEPENDENT", "UNKNOWN"] = "UNKNOWN"
    updated_at: datetime


class PolygonDirectoryPage(BaseModel):
    items: list[PolygonDirectoryItem] = Field(default_factory=list)
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
    next_offset: int | None = Field(default=None, ge=0)
