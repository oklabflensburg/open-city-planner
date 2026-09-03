POI_CATEGORY_LABELS: dict[str, str] = {
    "public_transport": "ÖPNV",
    "parking": "Parken",
    "gastronomy": "Gastronomie",
    "retail": "Einzelhandel",
    "groceries": "Lebensmittel",
    "education": "Bildung",
    "health": "Gesundheit",
    "culture": "Kultur",
    "leisure": "Freizeit",
    "finance": "Banken",
    "government": "Behörden",
    "hotels": "Hotels",
    "services": "Dienstleistungen",
    "tourism": "Tourismus",
    "public": "Öffentliche Einrichtungen",
    "building": "Gebäude",
    "landuse": "Flächennutzung",
}

# One canonical mapping shared by count and nearest-neighbour queries.
POI_CATEGORY_SQL = """
CASE
  WHEN tags->>'highway' = 'bus_stop' OR tags->>'public_transport' IN ('platform', 'station', 'stop_position') THEN 'public_transport'
  WHEN tags->>'amenity' IN ('parking', 'parking_entrance') THEN 'parking'
  WHEN tags->>'amenity' IN ('restaurant', 'cafe', 'fast_food', 'bar', 'pub', 'ice_cream') THEN 'gastronomy'
  WHEN tags->>'shop' IN ('supermarket', 'convenience', 'bakery', 'butcher', 'greengrocer', 'beverages') THEN 'groceries'
  WHEN tags ? 'shop' THEN 'retail'
  WHEN tags->>'amenity' IN ('school', 'kindergarten', 'college', 'university', 'library') THEN 'education'
  WHEN tags->>'amenity' IN ('hospital', 'clinic', 'doctors', 'dentist', 'pharmacy') THEN 'health'
  WHEN tags->>'amenity' IN ('theatre', 'cinema', 'arts_centre') OR tags->>'tourism' IN ('museum', 'gallery') THEN 'culture'
  WHEN tags ? 'leisure' THEN 'leisure'
  WHEN tags->>'amenity' IN ('bank', 'atm') THEN 'finance'
  WHEN tags->>'amenity' IN ('townhall', 'courthouse', 'police', 'post_office') OR tags->>'office' = 'government' THEN 'government'
  WHEN tags->>'tourism' IN ('hotel', 'hostel', 'guest_house') THEN 'hotels'
  ELSE NULL
END
"""

# The viewport extends the same POI taxonomy with non-POI polygon categories.
# Specific uses always win over generic building/landuse tags.
OSM_FEATURE_CATEGORY_SQL = """
CASE
  WHEN tags->>'highway' = 'bus_stop' OR tags->>'public_transport' IN ('platform', 'station', 'stop_position') OR tags ? 'railway' THEN 'public_transport'
  WHEN tags->>'amenity' IN ('parking', 'parking_entrance') OR tags ? 'parking' THEN 'parking'
  WHEN tags->>'amenity' IN ('restaurant', 'cafe', 'fast_food', 'bar', 'pub', 'ice_cream') THEN 'gastronomy'
  WHEN tags->>'shop' IN ('supermarket', 'convenience', 'bakery', 'butcher', 'greengrocer', 'beverages') THEN 'groceries'
  WHEN tags ? 'shop' THEN 'retail'
  WHEN tags->>'amenity' IN ('school', 'kindergarten', 'college', 'university', 'library') THEN 'education'
  WHEN tags->>'amenity' IN ('hospital', 'clinic', 'doctors', 'dentist', 'pharmacy') OR tags ? 'healthcare' THEN 'health'
  WHEN tags->>'amenity' IN ('theatre', 'cinema', 'arts_centre') OR tags->>'tourism' IN ('museum', 'gallery') OR tags ? 'historic' THEN 'culture'
  WHEN tags ? 'leisure' OR tags ? 'sport' OR tags ? 'club' THEN 'leisure'
  WHEN tags->>'amenity' IN ('bank', 'atm') THEN 'finance'
  WHEN tags->>'amenity' IN ('townhall', 'courthouse', 'police', 'post_office', 'fire_station') OR tags->>'office' = 'government' THEN 'government'
  WHEN tags->>'tourism' IN ('hotel', 'hostel', 'guest_house') THEN 'hotels'
  WHEN tags ? 'office' OR tags ? 'craft' THEN 'services'
  WHEN tags ? 'tourism' THEN 'tourism'
  WHEN tags ? 'amenity' THEN 'public'
  WHEN tags ? 'building' THEN 'building'
  WHEN tags ? 'landuse' OR tags ? 'natural' THEN 'landuse'
  ELSE NULL
END
"""

OSM_FEATURE_CATEGORIES = frozenset(POI_CATEGORY_LABELS)

# Semantic POI type exposed to map consumers. The precedence mirrors the
# existing ``primary_type`` response property while keeping OSM tag names an
# implementation detail of this provider.
POI_TYPE_SQL = """
COALESCE(tags->>'shop', tags->>'amenity', tags->>'office', tags->>'craft',
         tags->>'tourism', tags->>'leisure', tags->>'healthcare',
         tags->>'public_transport', tags->>'building', tags->>'landuse',
         tags->>'natural')
"""
