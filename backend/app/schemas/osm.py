from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OsmAddress(BaseModel):
    street: str | None = None
    house_number: str | None = None
    postal_code: str | None = None
    city: str | None = None


class OsmCentroid(BaseModel):
    longitude: float
    latitude: float


class OsmObjectInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    osm_id: int
    osm_type: Literal["node", "way", "relation"]
    name: str | None = None
    category: str | None = None
    shop: str | None = None
    amenity: str | None = None
    office: str | None = None
    craft: str | None = None
    tourism: str | None = None
    leisure: str | None = None
    building: str | None = None
    building_levels: str | None = None
    brand: str | None = None
    operator: str | None = None
    opening_hours: str | None = None
    website: str | None = None
    phone: str | None = None
    email: str | None = None
    wheelchair: str | None = None
    level: str | None = None
    indoor: str | None = None
    ref: str | None = None
    address: OsmAddress | None = None
    centroid: OsmCentroid | None = None
    overlap_ratio: float | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class PolygonOsmInfo(BaseModel):
    polygon_id: str
    polygon_slug: str
    source: Literal["local", "overpass", "none"]
    matches: list[OsmObjectInfo]
    primary_match: OsmObjectInfo | None = None
