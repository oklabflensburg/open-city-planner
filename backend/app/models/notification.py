import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    actor_type: Mapped[str] = mapped_column(String(16), default="SYSTEM", nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    priority: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    message: Mapped[str] = mapped_column(String(600), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(32))
    resource_id: Mapped[str | None] = mapped_column(String(160))
    resource_slug: Mapped[str | None] = mapped_column(String(255))
    action_url: Mapped[str | None] = mapped_column(String(500))
    action_label: Mapped[str | None] = mapped_column(String(80))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    in_app_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dedupe_key: Mapped[str | None] = mapped_column(String(255))
    event_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "category IN ('GIS','DATA','OSM','SOCIAL','ACCOUNT','ADMIN','SYSTEM')",
            name="ck_notifications_category",
        ),
        CheckConstraint(
            "priority IN ('INFO','SUCCESS','WARNING','ERROR','ACTION_REQUIRED')",
            name="ck_notifications_priority",
        ),
        CheckConstraint("actor_type IN ('USER','SYSTEM')", name="ck_notifications_actor_type"),
        Index("idx_notifications_recipient_created", "recipient_user_id", created_at.desc()),
        Index(
            "idx_notifications_recipient_unread_created",
            "recipient_user_id",
            "is_read",
            created_at.desc(),
        ),
        Index("idx_notifications_dedupe", "recipient_user_id", "dedupe_key", created_at.desc()),
    )


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_gis: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_osm: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_area_updates: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_social: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_account: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_notify_gis: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_notify_osm: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_notify_area_updates: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_notify_social: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_notify_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    newsletter_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class NotificationSubscription(Base):
    __tablename__ = "notification_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(160), nullable=False)
    event_types: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "resource_type", "resource_id", name="uq_notification_subscription_resource"
        ),
        Index("idx_notification_subscriptions_resource", "resource_type", "resource_id"),
    )
