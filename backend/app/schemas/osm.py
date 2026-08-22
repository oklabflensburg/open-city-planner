from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.external_links import ExternalLinks
from app.schemas.geojson import AreaGeometry


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
    occupancy_status: Literal["VACANT", "UNKNOWN"] = "UNKNOWN"
    occupancy_source: Literal["OSM"] | None = None
    occupancy_source_tag: str | None = None
    previous_osm_shop_type: str | None = None
    external_links: ExternalLinks = Field(default_factory=ExternalLinks)


class PolygonOsmInfo(BaseModel):
    polygon_id: str
    polygon_slug: str
    source: Literal["local", "overpass", "none"]
    matches: list[OsmObjectInfo]
    primary_match: OsmObjectInfo | None = None


class OsmViewportQuery(BaseModel):
    west: float = Field(ge=-180, le=180)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)
    zoom: float = Field(ge=0, le=24)
    osm_categories: str | None = None
    analysis_area: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,254}$")
    poi_category: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
    buildings: bool = False
    limit: int = Field(default=2_000, ge=1, le=2_500)

    @model_validator(mode="after")
    def validate_bbox(self) -> "OsmViewportQuery":
        if bool(self.analysis_area) != bool(self.poi_category):
            raise ValueError("Gebiet und Kategorie müssen gemeinsam angegeben werden")
        if self.west >= self.east:
            raise ValueError("West muss kleiner als Ost sein; Grenzen über den Antimeridian werden nicht unterstützt")
        if self.south >= self.north:
            raise ValueError("Süd muss kleiner als Nord sein")
        if self.zoom >= 11:
            max_span = 2_880 / (2 ** int(self.zoom))
            if self.east - self.west > max_span or self.north - self.south > max_span:
                raise ValueError("bounding box is too large for the requested zoom")
        return self


class OsmViewportProperties(BaseModel):
    feature_id: str
    osm_type: Literal["node", "way", "relation"]
    osm_id: int
    category: str
    canonical_category: str | None = None
    name: str | None = None
    primary_type: str | None = None
    natural: str | None = None
    feature_type: Literal["point", "polygon"]
    source: Literal["OSM"] = "OSM"
    canonical_floor: Literal["UG", "EG", "OG"] | None = None
    mapped_area_m2: float | None = None
    occupancy_status: Literal["VACANT", "UNKNOWN"] = "UNKNOWN"
    occupancy_source: Literal["OSM"] | None = None
    stadtplaner: list["OsmLinkedPolygon"] = Field(default_factory=list)
    external_links: ExternalLinks = Field(default_factory=ExternalLinks)


class OsmLinkedPolygon(BaseModel):
    id: str
    slug: str
    name: str
    floor: str | None = None


class OsmPolygonImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    osm_type: Literal["node", "way", "relation"]
    osm_id: int = Field(gt=0)
    floor: str | None = Field(default=None, max_length=16)
    geometry: AreaGeometry | None = None


class OsmPolygonImportRead(BaseModel):
    id: str
    slug: str
    geometry_source: Literal["osm_feature", "containing_osm_area", "manual"]
    source_osm_type: Literal["node", "way", "relation"]
    source_osm_id: int
    occupancy_status: Literal["OCCUPIED", "VACANT", "UNKNOWN"]
    occupancy_source: Literal["OSM", "UNKNOWN"]


class OsmViewportFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: dict[str, object]
    properties: OsmViewportProperties


class OsmViewportMeta(BaseModel):
    count: int
    truncated: bool
    zoom: float
    summary: dict[str, int]
    canonical_summary: dict[str, int] = Field(default_factory=dict)
    canonical_facets: dict[str, int] = Field(default_factory=dict)
    business_count: int = 0
    context_count: int = 0
    deduplicated_linked_count: int = 0
    osm_data_updated_at: datetime | None = None


class OsmViewportFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[OsmViewportFeature]
    meta: OsmViewportMeta
