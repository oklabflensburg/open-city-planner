from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

OccupancyStatus = Literal["OCCUPIED", "VACANT", "UNKNOWN"]


@dataclass(frozen=True)
class OsmOccupancyDetection:
    status: OccupancyStatus
    source_tag: str | None = None
    previous_shop_type: str | None = None
    lifecycle: str | None = None


def _value(tags: Mapping[str, Any], key: str) -> str | None:
    raw = tags.get(key)
    if raw is None:
        return None
    value = str(raw).strip().lower()
    return value or None


def detect_osm_occupancy_status(tags: Mapping[str, Any]) -> OsmOccupancyDetection:
    """Conservatively normalize public OSM lifecycle tags without a database lookup."""
    abandoned_shop = _value(tags, "abandoned:shop")
    if abandoned_shop or _value(tags, "abandoned") == "yes":
        tag = f"abandoned:shop={abandoned_shop}" if abandoned_shop else "abandoned=yes"
        return OsmOccupancyDetection("UNKNOWN", tag, abandoned_shop, "abandoned")

    disused_shop = _value(tags, "disused:shop")
    if disused_shop:
        return OsmOccupancyDetection(
            "VACANT", f"disused:shop={disused_shop}", disused_shop, "disused"
        )

    if _value(tags, "shop") == "vacant":
        return OsmOccupancyDetection("VACANT", "shop=vacant", lifecycle="vacant")

    if _value(tags, "disused") == "yes":
        shop = _value(tags, "shop")
        building = _value(tags, "building")
        landuse = _value(tags, "landuse")
        retail_context = bool(shop) or building in {"retail", "commercial"} or landuse in {
            "retail", "commercial"
        }
        if retail_context:
            return OsmOccupancyDetection("VACANT", "disused=yes", shop, "disused")
        return OsmOccupancyDetection("UNKNOWN", "disused=yes", lifecycle="disused")

    return OsmOccupancyDetection("UNKNOWN")
