from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Position = tuple[float, float]


class PolygonGeometry(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[Position]]

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, rings: list[list[Position]]) -> list[list[Position]]:
        if not rings:
            raise ValueError("Polygon requires at least one linear ring")
        for ring in rings:
            if len(ring) < 4:
                raise ValueError("Linear rings need at least four positions")
            if ring[0] != ring[-1]:
                raise ValueError("Lineare Ringe müssen geschlossen sein")
            for lng, lat in ring:
                if not -180 <= lng <= 180 or not -90 <= lat <= 90:
                    raise ValueError("Coordinates must use EPSG:4326 longitude/latitude ranges")
        vertex_count = sum(len(ring) for ring in rings)
        if vertex_count > 5000:
            raise ValueError("Polygon exceeds maximum vertex count")
        return rings


class MultiPolygonGeometry(BaseModel):
    type: Literal["MultiPolygon"]
    coordinates: list[list[list[Position]]]

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, polygons: list[list[list[Position]]]) -> list[list[list[Position]]]:
        if not polygons:
            raise ValueError("MultiPolygon requires at least one polygon")
        for rings in polygons:
            PolygonGeometry(type="Polygon", coordinates=rings)
        if sum(len(ring) for polygon in polygons for ring in polygon) > 10_000:
            raise ValueError("MultiPolygon exceeds maximum vertex count")
        return polygons


AreaGeometry = PolygonGeometry | MultiPolygonGeometry


class Feature(BaseModel):
    type: Literal["Feature"]
    id: str | None = None
    geometry: AreaGeometry
    properties: dict[str, Any] = Field(default_factory=dict)


class FeatureCollection(BaseModel):
    type: Literal["FeatureCollection"]
    features: list[Feature]


class PolygonBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    category: str = Field(default="custom", min_length=1, max_length=80)
    geometry: AreaGeometry
    properties: dict[str, Any] = Field(default_factory=dict)
    floor: str | None = Field(default=None, max_length=16)


class PolygonCreate(PolygonBase):
    pass


class PolygonUpdate(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    category: str | None = Field(default=None, min_length=1, max_length=80)
    geometry: AreaGeometry | None = None
    properties: dict[str, Any] | None = None
    floor: str | None = Field(default=None, max_length=16)
    area_size: Literal["S", "M", "L", "XL"] | None = None
    expected_updated_at: datetime | None = None

    @model_validator(mode="after")
    def require_any_field(self) -> "PolygonUpdate":
        editable = {"name", "description", "category", "geometry", "properties", "floor", "area_size"}
        if not self.model_fields_set.intersection(editable) and not self.model_extra:
            raise ValueError("Mindestens ein Feld muss angegeben werden")
        return self


class PolygonRead(PolygonBase):
    id: str
    slug: str
    created_by_user_id: str | None = None
    updated_by_user_id: str | None = None
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class PolygonOverviewRead(BaseModel):
    id: str
    slug: str
    name: str
    category: str
    floor: str | None
    area_size: str | None
    address_display_name: str | None
    occupancy_status: Literal["OCCUPIED", "VACANT", "UNKNOWN"] = "UNKNOWN"
    business_structure: Literal["CHAIN", "INDEPENDENT", "UNKNOWN"] = "UNKNOWN"
    geometry: AreaGeometry
    created_at: datetime
    updated_at: datetime


class PolygonMetrics(BaseModel):
    area_m2: float
    perimeter_m: float
    centroid: Position
    bbox: tuple[float, float, float, float]


class PolygonOsmSourceRead(BaseModel):
    osm_type: Literal["node", "way", "relation"]
    osm_id: int
    is_primary: bool
    imported_at: datetime


class PublicPolygonDetail(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None
    floor: str | None
    area_size: Literal["S", "M", "L", "XL"] | None
    address_display_name: str | None
    address_street: str | None
    address_house_number: str | None
    address_postal_code: str | None
    address_city: str | None
    address_country: str | None
    address_lookup_status: str
    category: str
    occupancy_status: Literal["OCCUPIED", "VACANT", "UNKNOWN"] = "UNKNOWN"
    occupancy_source: Literal["OSM", "MANUAL", "IMPORTED", "CALCULATED", "UNKNOWN"] = "UNKNOWN"
    business_structure: Literal["CHAIN", "INDEPENDENT", "UNKNOWN"] = "UNKNOWN"
    geometry: AreaGeometry
    area_m2: float
    perimeter_m: float
    centroid: Position
    bbox: tuple[float, float, float, float]
    created_at: datetime
    updated_at: datetime
    osm_sources: list[PolygonOsmSourceRead] = Field(default_factory=list)


class PolygonEditorRead(PublicPolygonDetail):
    can_edit_public_fields: bool = True
    can_delete: bool = False


class PolygonVerwaltungRead(PublicPolygonDetail):
    owner_name: str | None
    owner_street: str | None
    owner_house_number: str | None
    owner_postal_code: str | None
    owner_city: str | None
    owner_country: str | None
    price_per_sqm: Decimal | None
    occupancy_source_tag: str | None
    occupancy_source_updated_at: datetime | None
    created_by_user_id: str | None
    updated_by_user_id: str | None


class PolygonVerwaltungUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_name: str | None = Field(default=None, max_length=200)
    owner_street: str | None = Field(default=None, max_length=160)
    owner_house_number: str | None = Field(default=None, max_length=40)
    owner_postal_code: str | None = Field(default=None, max_length=32)
    owner_city: str | None = Field(default=None, max_length=120)
    owner_country: str | None = Field(default=None, max_length=120)
    price_per_sqm: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    occupancy_status: Literal["OCCUPIED", "VACANT", "UNKNOWN"] | None = None
    business_structure: Literal["CHAIN", "INDEPENDENT", "UNKNOWN"] | None = None
    expected_updated_at: datetime | None = None

    @field_validator(
        "owner_name",
        "owner_street",
        "owner_house_number",
        "owner_postal_code",
        "owner_city",
        "owner_country",
    )
    @classmethod
    def trim_management_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def require_management_field(self) -> "PolygonVerwaltungUpdate":
        if not (self.model_fields_set - {"expected_updated_at"}):
            raise ValueError("Mindestens ein Verwaltungsfeld muss angegeben werden")
        return self


class PolygonSitemapEntry(BaseModel):
    slug: str
    updated_at: datetime
