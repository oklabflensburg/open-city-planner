from collections.abc import Mapping
from typing import Any

OSM_EXCLUDED_FEATURES = frozenset({("natural", "peninsula")})


def should_exclude_osm_feature(tags: Mapping[str, Any]) -> bool:
    """Return whether an OSM object must stay out of interactive feature flows."""
    return any(
        str(tags.get(key, "")).strip().lower() == excluded_value
        for key, excluded_value in OSM_EXCLUDED_FEATURES
    )
