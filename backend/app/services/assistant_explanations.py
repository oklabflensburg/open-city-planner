from typing import Any

from app.services.osm_canonical import (
    GASTRONOMY_AMENITIES,
    SERVICE_AMENITIES,
    SERVICE_SHOPS,
    SHOP_CATEGORIES,
    osm_business_category,
)
from app.services.osm_occupancy import detect_osm_occupancy_status


def explain_osm_feature(data: dict[str, Any]) -> dict[str, Any]:
    tags = {str(key): str(value) for key, value in (data.get("tags") or {}).items()}
    category = osm_business_category(tags)
    occupancy = detect_osm_occupancy_status(tags)
    category_rule = _category_rule(tags, category)
    occupancy_rule = _occupancy_rule(occupancy.status, occupancy.source_tag)
    return {
        "osm_type": data.get("osm_type"),
        "osm_id": data.get("osm_id"),
        "name": data.get("name"),
        "category": category,
        "category_explanation": category_rule,
        "occupancy_status": occupancy.status,
        "occupancy_explanation": occupancy_rule,
        "evidence_tags": [
            value for value in (_category_source_tag(tags, category), occupancy.source_tag) if value
        ],
    }


def _category_source_tag(tags: dict[str, str], category: str | None) -> str | None:
    shop = tags.get("shop")
    if shop and shop != "vacant":
        return f"shop={shop}"
    for key in ("disused:shop", "abandoned:shop"):
        if tags.get(key):
            return f"{key}={tags[key]}"
    amenity = tags.get("amenity")
    if amenity and category:
        return f"amenity={amenity}"
    for key in ("office", "craft"):
        if tags.get(key):
            return f"{key}={tags[key]}"
    return None


def _category_rule(tags: dict[str, str], category: str | None) -> str:
    source_tag = _category_source_tag(tags, category)
    if category is None:
        return "Für dieses Objekt greift keine kanonische Geschäftskategorie des Stadtplaners."
    if tags.get("amenity") in GASTRONOMY_AMENITIES:
        return f"Das Objekt wird als Gastronomie eingeordnet, weil {source_tag} hinterlegt ist."
    shop = tags.get("shop") or tags.get("disused:shop") or tags.get("abandoned:shop")
    if shop in SHOP_CATEGORIES.get(category, frozenset()) or shop in SERVICE_SHOPS:
        return f"Das Objekt wird der Kategorie {category} zugeordnet, weil {source_tag} hinterlegt ist."
    if tags.get("amenity") in SERVICE_AMENITIES or tags.get("office") or tags.get("craft"):
        return f"Das Objekt wird als Dienstleistung eingeordnet, weil {source_tag} hinterlegt ist."
    if source_tag:
        return f"Die kanonische Stadtplaner-Regel ordnet {source_tag} der Kategorie {category} zu."
    return f"Die kanonische Stadtplaner-Regel ordnet das Objekt der Kategorie {category} zu."


def _occupancy_rule(status: str, source_tag: str | None) -> str:
    if status == "VACANT" and source_tag:
        return f"Das Objekt wird als leerstehend eingeordnet, weil {source_tag} hinterlegt ist."
    if source_tag and source_tag.startswith("abandoned"):
        return (
            f"{source_tag} beschreibt einen aufgegebenen Zustand. Der Stadtplaner behandelt "
            "ihn konservativ als UNKNOWN und nicht automatisch als belegt oder leerstehend."
        )
    if source_tag == "disused=yes":
        return "disused=yes reicht ohne vorhandenen Gewerbekontext nicht für eine sichere Leerstandserkennung aus."
    return "Der Belegungsstatus ist unbekannt; aus fehlenden Leerstandstags wird nicht OCCUPIED abgeleitet."
