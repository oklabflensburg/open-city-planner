import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SocialPublicationOutbox(Base):
    __tablename__ = "social_publication_outbox"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(24), default="MASTODON", nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    mastodon_status_id: Mapped[str | None] = mapped_column(String(120))
    mastodon_status_url: Mapped[str | None] = mapped_column(Text)
    mastodon_media_id: Mapped[str | None] = mapped_column(String(120))
    screenshot_path: Mapped[str | None] = mapped_column(Text)
    screenshot_target_url: Mapped[str | None] = mapped_column(Text)
    screenshot_alt_text: Mapped[str | None] = mapped_column(Text)
    screenshot_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING_APPROVAL','PENDING','PROCESSING','PUBLISHED','FAILED','CANCELLED','DRY_RUN')",
            name="ck_social_outbox_status",
        ),
        Index("idx_social_outbox_due", "status", "next_attempt_at"),
        Index("idx_social_outbox_resource", "resource_type", "resource_id"),
        Index(
            "uq_social_outbox_pending_resource",
            "platform", "resource_type", "resource_id",
            unique=True,
            postgresql_where=(status.in_(("PENDING", "PENDING_APPROVAL"))),
        ),
        Index(
            "uq_social_outbox_polygon_adopted",
            "event_type", "resource_id",
            unique=True,
            postgresql_where=text("event_type = 'POLYGON_ADOPTED_FROM_OSM'"),
        ),
    )


class SocialPublication(Base):
    __tablename__ = "social_publications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    outbox_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    platform: Mapped[str] = mapped_column(String(24), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    remote_id: Mapped[str | None] = mapped_column(String(120))
    remote_url: Mapped[str | None] = mapped_column(Text)
    remote_media_id: Mapped[str | None] = mapped_column(String(120))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("content_hash", "resource_id", "event_type", name="uq_social_publication_content"),
        Index("idx_social_publications_published", "published_at"),
    )


class SocialPublishingSettings(Base):
    __tablename__ = "social_publishing_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(24), nullable=False, unique=True, default="MASTODON")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    approval_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="AUTOMATIC")
    default_visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="public")
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="de")
    debounce_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    default_hashtags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    enabled_events: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    screenshot_viewport: Mapped[str] = mapped_column(String(16), nullable=False, default="LANDSCAPE_16_9")
    screenshot_show_map: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    screenshot_show_facts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    screenshot_show_pois: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    screenshot_show_branding: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    polygon_osm_adoption_link_target: Mapped[str] = mapped_column(
        String(16), nullable=False, default="DETAIL_PAGE"
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("approval_mode IN ('AUTOMATIC','MANUAL','DRY_RUN')", name="ck_social_settings_approval"),
        CheckConstraint("default_visibility IN ('public','unlisted','private')", name="ck_social_settings_visibility"),
        CheckConstraint("debounce_seconds BETWEEN 0 AND 86400", name="ck_social_settings_debounce"),
        CheckConstraint(
            "screenshot_viewport IN ('LANDSCAPE_16_9','LANDSCAPE_OG','SQUARE')",
            name="ck_social_settings_viewport",
        ),
        CheckConstraint(
            "polygon_osm_adoption_link_target IN ('DETAIL_PAGE','GIS')",
            name="ck_social_settings_polygon_link_target",
        ),
    )
