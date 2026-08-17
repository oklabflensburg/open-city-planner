from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class MastodonAdminStatusRead(BaseModel):
    enabled: bool
    configured: bool
    reachable: bool | None
    account: str
    account_url: str
    area_updates_enabled: bool
    dry_run: bool
    visibility: str
    pending: int = 0
    failed: int = 0
    published: int = 0
    last_publication_at: datetime | None = None
    verification_error: str | None = None
    approval_mode: str = "AUTOMATIC"
    screenshots_required: bool = True


class SocialPublicationItemRead(BaseModel):
    id: UUID
    created_at: datetime
    event_type: str
    resource_type: str
    resource_id: UUID | None
    resource_name: str
    resource_slug: str | None
    status: str
    attempt_count: int
    next_attempt_at: datetime
    published_at: datetime | None
    last_error: str | None
    remote_url: str | None
    changed_fields: list[str] = Field(default_factory=list)
    dry_run: bool
    screenshot_ready: bool = False
    screenshot_target_url: str | None = None
    screenshot_alt_text: str | None = None


class SocialPublicationListRead(BaseModel):
    items: list[SocialPublicationItemRead]
    total: int
    page: int
    page_size: int
    pages: int


class SocialEventDefinitionRead(BaseModel):
    event_type: str
    topic: str
    topic_label: str
    label: str
    description: str
    default_enabled: bool


class SocialPublishingSettingsRead(BaseModel):
    enabled: bool
    approval_mode: str
    default_visibility: str
    language: str
    debounce_seconds: int
    default_hashtags: list[str]
    enabled_events: list[str]
    screenshot_viewport: str
    screenshot_show_map: bool
    screenshot_show_facts: bool
    screenshot_show_pois: bool
    screenshot_show_branding: bool
    polygon_osm_adoption_link_target: Literal["DETAIL_PAGE", "GIS"] = "DETAIL_PAGE"
    screenshots_required: bool = True
    registry: list[SocialEventDefinitionRead]
    updated_at: datetime


class SocialPublishingSettingsUpdate(BaseModel):
    enabled: bool | None = None
    approval_mode: Literal["AUTOMATIC", "MANUAL", "DRY_RUN"] | None = None
    default_visibility: Literal["public", "unlisted", "private"] | None = None
    language: Literal["de"] | None = None
    debounce_seconds: int | None = Field(default=None, ge=0, le=86400)
    default_hashtags: list[str] | None = Field(default=None, max_length=5)
    enabled_events: list[str] | None = None
    screenshot_viewport: Literal["LANDSCAPE_16_9", "LANDSCAPE_OG", "SQUARE"] | None = None
    screenshot_show_map: bool | None = None
    screenshot_show_facts: bool | None = None
    screenshot_show_pois: bool | None = None
    screenshot_show_branding: bool | None = None
    polygon_osm_adoption_link_target: Literal["DETAIL_PAGE", "GIS"] | None = None

    @model_validator(mode="after")
    def validate_partial_update(self) -> "SocialPublishingSettingsUpdate":
        if not self.model_fields_set:
            raise ValueError("Mindestens eine Social-Publishing-Einstellung ist erforderlich")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Social-Publishing-Einstellungen dürfen nicht null sein")
        return self

    @field_validator("default_hashtags")
    @classmethod
    def validate_hashtags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = []
        for item in value:
            tag = item.strip().lstrip("#")
            if not tag or len(tag) > 40 or not tag.replace("_", "").isalnum():
                raise ValueError("Hashtags dürfen nur Buchstaben, Zahlen und Unterstriche enthalten")
            if tag not in cleaned:
                cleaned.append(tag)
        return cleaned


class SocialPublicationPreviewRead(BaseModel):
    id: UUID
    text: str
    target_url: str
    target_label: str = "Öffentliche Gebietsseite"
    event_type: str
    resource_name: str
    hashtags: list[str]
    screenshot_ready: bool
    screenshot_url: str | None
    alt_text: str


class SocialPublicationApprovalUpdate(BaseModel):
    alt_text: str = Field(min_length=1, max_length=1500)

    @field_validator("alt_text")
    @classmethod
    def validate_alt_text(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Die Bildbeschreibung darf nicht leer sein")
        return cleaned


class PublicAdoptedPolygonSnapshot(BaseModel):
    """Strict allowlist for data that may enter a polygon-adoption publication."""

    model_config = {"extra": "forbid"}

    polygon_id: UUID
    slug: str
    title: str
    category: str
    floor: str | None
    area_size: Literal["S", "M", "L", "XL"] | None
    address: str | None
    occupancy_status: Literal["OCCUPIED", "VACANT", "UNKNOWN"]
    osm_type: Literal["node", "way", "relation"]
    osm_id: int
