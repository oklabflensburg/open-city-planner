from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.social_publication import SocialPublishingSettings


@dataclass(frozen=True)
class SocialEventDefinition:
    event_type: str
    topic: str
    topic_label: str
    label: str
    description: str
    default_enabled: bool


SOCIAL_EVENT_REGISTRY = (
    SocialEventDefinition("AREA_CREATED", "AREAS", "Gebiete", "Neue Gebiete", "Neue öffentliche Gemeinden, Stadtteile und Quartiere.", True),
    SocialEventDefinition("AREA_PUBLIC_DATA_UPDATED", "AREAS", "Gebiete", "Gebietsdaten", "Wesentliche Änderungen sichtbarer Gebietsdaten.", True),
    SocialEventDefinition("AREA_BOUNDARY_UPDATED", "AREAS", "Gebiete", "Gebietsgrenzen", "Grenzänderungen oberhalb des fachlichen Schwellenwerts.", True),
    SocialEventDefinition("AREA_STATISTICS_UPDATED", "STATISTICS", "Statistik", "Gebietskennzahlen", "Bewusst klassifizierte Änderungen öffentlicher Kennzahlen.", True),
    SocialEventDefinition("AREA_STATISTICS_BULK_UPDATED", "STATISTICS", "Statistik", "Kommunale Statistikdaten", "Ein Sammelhinweis pro Statistikimport.", True),
    SocialEventDefinition(
        "POLYGON_ADOPTED_FROM_OSM", "POLYGONS", "Flächen", "Neue OSM-Flächen",
        "Ein einmaliger Hinweis, wenn eine OSM-Fläche bewusst in Stadtplaner übernommen wurde.", False,
    ),
)
KNOWN_SOCIAL_EVENTS = frozenset(item.event_type for item in SOCIAL_EVENT_REGISTRY)
DEFAULT_ENABLED_EVENTS = [item.event_type for item in SOCIAL_EVENT_REGISTRY if item.default_enabled]
VIEWPORTS = {
    "LANDSCAPE_16_9": (1200, 675),
    "LANDSCAPE_OG": (1200, 630),
    "SQUARE": (1080, 1080),
}


def default_social_settings(env: Settings) -> SocialPublishingSettings:
    return SocialPublishingSettings(
        platform="MASTODON",
        enabled=env.mastodon_area_updates_enabled,
        approval_mode="DRY_RUN" if env.mastodon_dry_run else "AUTOMATIC",
        default_visibility=env.mastodon_default_visibility,
        language="de",
        debounce_seconds=env.mastodon_area_update_debounce_seconds,
        default_hashtags=env.mastodon_hashtag_list,
        enabled_events=DEFAULT_ENABLED_EVENTS,
        screenshot_viewport="LANDSCAPE_16_9",
        screenshot_show_map=True,
        screenshot_show_facts=True,
        screenshot_show_pois=False,
        screenshot_show_branding=True,
        polygon_osm_adoption_link_target="DETAIL_PAGE",
    )


async def get_social_settings(
    session: AsyncSession,
    env: Settings,
    *,
    create: bool = True,
) -> SocialPublishingSettings:
    model = await session.scalar(
        select(SocialPublishingSettings).where(SocialPublishingSettings.platform == "MASTODON")
    )
    if model is not None:
        return model
    model = default_social_settings(env)
    if create:
        session.add(model)
        await session.flush()
    return model


def event_is_enabled(policy: SocialPublishingSettings, event_type: str) -> bool:
    return event_type in KNOWN_SOCIAL_EVENTS and event_type in set(policy.enabled_events or [])


def enabled_event_types(policy: SocialPublishingSettings) -> set[str]:
    return set(policy.enabled_events or []) & KNOWN_SOCIAL_EVENTS
