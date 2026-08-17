from collections.abc import Mapping
from typing import Any

from app.services.osm_occupancy import detect_osm_occupancy_status

# This taxonomy is shared with Stadtplaner polygons. The values are based on the
# locally imported Flensburg tag inventory; unknown shop values deliberately fall
# back to "other" instead of disappearing.
SHOP_CATEGORIES: dict[str, frozenset[str]] = {
    "warehouse": frozenset({"department_store", "mall", "variety_store"}),
    "fashion": frozenset({
        "boutique", "clothes", "fabric", "fashion", "fashion_accessories",
        "jewelry", "leather", "shoes",
    }),
    "food": frozenset({
        "alcohol", "bakery", "beverages", "butcher", "chemist", "coffee",
        "confectionery", "convenience", "cosmetics", "deli", "farm", "food",
        "greengrocer", "nutrition_supplements", "perfumery", "seafood",
        "supermarket", "tea", "tobacco", "wine",
    }),
    "electronics": frozenset({
        "appliance", "computer", "electrical", "electronics", "mobile_phone",
        "telecommunication",
    }),
    "furniture": frozenset({
        "bathroom_furnishing", "carpet", "furniture", "houseware",
        "interior_decoration", "kitchen",
    }),
    "garden": frozenset({
        "bicycle", "doityourself", "equestrian", "fishing", "florist",
        "garden_centre", "outdoor", "pet", "sports", "toys",
    }),
}

GASTRONOMY_AMENITIES = frozenset({
    "bar", "cafe", "fast_food", "ice_cream", "pub", "restaurant",
})
SERVICE_AMENITIES = frozenset({"bank", "pharmacy"})
SERVICE_SHOPS = frozenset({
    "beauty", "copyshop", "estate_agent", "funeral_directors", "hairdresser",
    "laundry", "massage", "tailor", "tattoo", "travel_agency",
})


def _value(tags: Mapping[str, Any], key: str) -> str | None:
    value = tags.get(key)
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return normalized or None


def osm_business_category(tags: Mapping[str, Any]) -> str | None:
    """Return a Stadtplaner category for retail-related OSM features only."""
    shop = _value(tags, "shop")
    if shop == "vacant":
        shop = None
    shop = shop or _value(tags, "disused:shop") or _value(tags, "abandoned:shop")
    amenity = _value(tags, "amenity")
    for category, values in SHOP_CATEGORIES.items():
        if shop in values:
            return category
    if shop in SERVICE_SHOPS:
        return "services"
    if amenity in GASTRONOMY_AMENITIES:
        return "gastronomy"
    if _value(tags, "office") or _value(tags, "craft") or amenity in SERVICE_AMENITIES:
        return "services"
    if shop:
        return "other"
    if _value(tags, "shop") == "vacant":
        return "otherAreas"
    return None


def osm_floor_group(tags: Mapping[str, Any]) -> str | None:
    """Normalize only a feature's explicit level; building:levels is not a shop level."""
    level = _value(tags, "level")
    if level is None or not level.lstrip("-").isdigit():
        return None
    number = int(level)
    if number < 0:
        return "UG"
    if number == 0:
        return "EG"
    return "OG"


def osm_status(tags: Mapping[str, Any]) -> str:
    return detect_osm_occupancy_status(tags).status


def _sql_values(values: frozenset[str]) -> str:
    return ", ".join(f"'{value}'" for value in sorted(values))


def osm_business_category_sql(tags: str = "osm.tags") -> str:
    raw_shop = (
        f"COALESCE(NULLIF(lower({tags}->>'shop'), 'vacant'), "
        f"lower({tags}->>'disused:shop'), lower({tags}->>'abandoned:shop'))"
    )
    cases = "\n".join(
        f"WHEN {raw_shop} IN ({_sql_values(values)}) THEN '{category}'"
        for category, values in SHOP_CATEGORIES.items()
    )
    return f"""CASE
      {cases}
      WHEN {raw_shop} IN ({_sql_values(SERVICE_SHOPS)}) THEN 'services'
      WHEN lower({tags}->>'amenity') IN ({_sql_values(GASTRONOMY_AMENITIES)}) THEN 'gastronomy'
      WHEN {tags} ? 'office' OR {tags} ? 'craft'
        OR lower({tags}->>'amenity') IN ({_sql_values(SERVICE_AMENITIES)}) THEN 'services'
      WHEN {raw_shop} IS NOT NULL THEN 'other'
      WHEN lower({tags}->>'shop') = 'vacant' THEN 'otherAreas'
      ELSE NULL
    END"""


def osm_floor_group_sql(tags: str = "osm.tags") -> str:
    level = f"NULLIF(trim({tags}->>'level'), '')"
    return f"""CASE
      WHEN {level} ~ '^-?[0-9]+$' AND ({level})::integer < 0 THEN 'UG'
      WHEN {level} ~ '^-?[0-9]+$' AND ({level})::integer = 0 THEN 'EG'
      WHEN {level} ~ '^-?[0-9]+$' AND ({level})::integer > 0 THEN 'OG'
      ELSE NULL
    END"""


def osm_status_sql(tags: str = "osm.tags") -> str:
    return f"""CASE
      WHEN {tags} ? 'abandoned:shop' OR lower({tags}->>'abandoned') = 'yes' THEN 'UNKNOWN'
      WHEN {tags} ? 'disused:shop' OR lower({tags}->>'shop') = 'vacant' THEN 'VACANT'
      WHEN lower({tags}->>'disused') = 'yes' AND (
        {tags} ? 'shop' OR lower({tags}->>'building') IN ('retail', 'commercial')
        OR lower({tags}->>'landuse') IN ('retail', 'commercial')
      ) THEN 'VACANT'
      ELSE 'UNKNOWN'
    END"""
