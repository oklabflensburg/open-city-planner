from collections.abc import Mapping
from typing import Any
from urllib.parse import quote, unquote

from app.schemas.external_links import ExternalLinks, WikipediaExternalLink


def wikipedia_title(value: str | None) -> str | None:
    """Return a safe German article title from the OSM wikipedia tag syntax."""
    if not value:
        return None
    value = value.strip()
    if value.startswith("de:"):
        return value[3:].strip().replace("_", " ") or None
    prefix = "https://de.wikipedia.org/wiki/"
    if value.startswith(prefix):
        return unquote(value[len(prefix) :]).replace("_", " ") or None
    return None


def external_links_from_osm_tags(tags: Mapping[str, Any]) -> ExternalLinks:
    """Build allowlisted URLs only; never render an arbitrary URL from OSM."""
    title = wikipedia_title(str(tags.get("wikipedia") or "").strip() or None)
    return ExternalLinks(
        wikipedia=(
            WikipediaExternalLink(
                title=title,
                url=f"https://de.wikipedia.org/wiki/{quote(title.replace(' ', '_'), safe='()_-')}",
            )
            if title
            else None
        ),
    )
