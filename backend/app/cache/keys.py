import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

from app.core.config import get_settings

CACHE_SCHEMA_VERSION = "v1"


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in sorted(value.items())}
    if isinstance(value, (set, frozenset)):
        return sorted(_canonical(item) for item in value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return sorted((_canonical(item) for item in value), key=lambda item: str(item))
    return str(value) if hasattr(value, "hex") and not isinstance(value, (str, bytes)) else value


def build_cache_key(resource: str, params: Mapping[str, Any], *, version: int | str) -> str:
    canonical = json.dumps(
        _canonical(params), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    prefix = get_settings().cache_prefix.strip(":")
    return f"{prefix}:{CACHE_SCHEMA_VERSION}:{resource}:v{version}:{digest}"


def longitude_to_tile_x(longitude: float, zoom: int) -> int:
    size = 2**zoom
    return min(size - 1, max(0, int((longitude + 180.0) / 360.0 * size)))


def latitude_to_tile_y(latitude: float, zoom: int) -> int:
    latitude = min(85.05112878, max(-85.05112878, latitude))
    radians = math.radians(latitude)
    size = 2**zoom
    return min(
        size - 1,
        max(0, int((1 - math.asinh(math.tan(radians)) / math.pi) / 2 * size)),
    )


def tile_x_to_longitude(x: int, zoom: int) -> float:
    return x / (2**zoom) * 360.0 - 180.0


def tile_y_to_latitude(y: int, zoom: int) -> float:
    value = math.pi * (1 - 2 * y / (2**zoom))
    return math.degrees(math.atan(math.sinh(value)))


def viewport_tile_bucket(
    west: float, south: float, east: float, north: float, zoom: float
) -> dict[str, int | float]:
    # Two levels finer than the display zoom limits bucket overfetch while retaining reuse.
    tile_zoom = min(19, max(13, math.floor(zoom) + 2))
    x_min = longitude_to_tile_x(west, tile_zoom)
    x_max = longitude_to_tile_x(east, tile_zoom)
    y_min = latitude_to_tile_y(north, tile_zoom)
    y_max = latitude_to_tile_y(south, tile_zoom)
    return {
        "tile_zoom": tile_zoom,
        "x_min": x_min,
        "x_max": x_max,
        "y_min": y_min,
        "y_max": y_max,
        "west": tile_x_to_longitude(x_min, tile_zoom),
        "east": tile_x_to_longitude(x_max + 1, tile_zoom),
        "north": tile_y_to_latitude(y_min, tile_zoom),
        "south": tile_y_to_latitude(y_max + 1, tile_zoom),
    }
