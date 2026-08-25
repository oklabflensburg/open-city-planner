"""Producer-owned Polygon-Eventverträge ohne Kenntnis konkreter Consumer."""

import uuid
from dataclasses import dataclass
from typing import ClassVar

from app.platform.modules.sdk import JsonValue


@dataclass(frozen=True, slots=True)
class PolygonCreated:
    polygon_id: uuid.UUID
    event_name: ClassVar[str] = "polygons.created"
    event_version: ClassVar[int] = 1

    def to_payload(self) -> dict[str, JsonValue]:
        return {"polygon_id": str(self.polygon_id)}


@dataclass(frozen=True, slots=True)
class PolygonUpdated:
    polygon_id: uuid.UUID
    geometry_changed: bool
    occupancy_status_changed: bool
    actor_user_id: uuid.UUID | None
    event_name: ClassVar[str] = "polygons.updated"
    event_version: ClassVar[int] = 1

    def to_payload(self) -> dict[str, JsonValue]:
        return {
            "polygon_id": str(self.polygon_id),
            "geometry_changed": self.geometry_changed,
            "occupancy_status_changed": self.occupancy_status_changed,
            "actor_user_id": str(self.actor_user_id) if self.actor_user_id else None,
        }


@dataclass(frozen=True, slots=True)
class PolygonDeleted:
    polygon_id: uuid.UUID
    deleted_by_user_id: uuid.UUID
    created_by_user_id: uuid.UUID | None
    slug: str | None
    name: str
    event_name: ClassVar[str] = "polygons.deleted"
    event_version: ClassVar[int] = 1

    def to_payload(self) -> dict[str, JsonValue]:
        return {
            "polygon_id": str(self.polygon_id),
            "deleted_by_user_id": str(self.deleted_by_user_id),
            "created_by_user_id": (
                str(self.created_by_user_id) if self.created_by_user_id else None
            ),
            "slug": self.slug,
            "name": self.name,
        }
