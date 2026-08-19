import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NotificationCategory = Literal["GIS", "DATA", "OSM", "SOCIAL", "ACCOUNT", "ADMIN", "SYSTEM"]
NotificationPriority = Literal["INFO", "SUCCESS", "WARNING", "ERROR", "ACTION_REQUIRED"]


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    category: NotificationCategory
    priority: NotificationPriority
    title: str
    message: str
    resource_type: str | None = None
    resource_id: str | None = None
    resource_slug: str | None = None
    action_url: str | None = None
    action_label: str | None = None
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime
    metadata: dict = Field(default_factory=dict, validation_alias="event_metadata")


class NotificationPage(BaseModel):
    items: list[NotificationRead]
    total: int
    unread_count: int
    page: int
    page_size: int
    pages: int


class UnreadCountRead(BaseModel):
    unread_count: int


class NotificationPreferencesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    in_app_enabled: bool = True
    notify_gis: bool = True
    notify_osm: bool = True
    notify_area_updates: bool = True
    notify_social: bool = True
    notify_account: bool = True
    notify_system: bool = True
    email_enabled: bool = False
    email_notify_gis: bool = False
    email_notify_osm: bool = False
    email_notify_area_updates: bool = False
    email_notify_social: bool = False
    email_notify_system: bool = False
    newsletter_enabled: bool = False
    updated_at: datetime | None = None


class NotificationPreferencesUpdate(BaseModel):
    in_app_enabled: bool | None = None
    notify_gis: bool | None = None
    notify_osm: bool | None = None
    notify_area_updates: bool | None = None
    notify_social: bool | None = None
    notify_account: bool | None = None
    notify_system: bool | None = None
    email_enabled: bool | None = None
    email_notify_gis: bool | None = None
    email_notify_osm: bool | None = None
    email_notify_area_updates: bool | None = None
    email_notify_social: bool | None = None
    email_notify_system: bool | None = None
    newsletter_enabled: bool | None = None


class NotificationSubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    resource_type: str
    resource_id: str
    event_types: list[str]
    created_at: datetime


class NotificationSubscriptionUpdate(BaseModel):
    resource_type: Literal["POLYGON", "AREA"]
    resource_id: str = Field(min_length=1, max_length=160)
    event_types: list[str] = Field(default_factory=list, max_length=20)
