"""Vom Referenzmodul besessene, serialisierbare Domain Events."""

from dataclasses import dataclass
from typing import ClassVar

from app.platform.modules.sdk import JsonValue


@dataclass(frozen=True, slots=True)
class ReferenceItemCreated:
    item_id: str
    title: str

    event_name: ClassVar[str] = "reference.item-created"
    event_version: ClassVar[int] = 1

    def to_payload(self) -> dict[str, JsonValue]:
        return {"item_id": self.item_id, "title": self.title}
