"""Public, persistence-free contracts exposed to other modules."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

SERVICE_ID = "analysis-areas.lookup"
SERVICE_VERSION = 1


@dataclass(frozen=True, slots=True)
class AnalysisAreaSummary:
    id: str
    slug: str
    name: str
    area_type: str
    parent_id: str | None


@dataclass(frozen=True, slots=True)
class AnalysisAreaGeometry:
    id: str
    slug: str
    geometry: dict[str, object]


class AnalysisAreaQueryService(Protocol):
    async def list_areas(
        self, *, area_type: str | None = None, parent_id: str | None = None
    ) -> Sequence[AnalysisAreaSummary]: ...

    async def get_by_id(self, area_id: str) -> AnalysisAreaSummary | None: ...

    async def get_by_slug(self, slug: str) -> AnalysisAreaSummary | None: ...

    async def get_geometry(self, slug: str) -> AnalysisAreaGeometry | None: ...

    async def get_parent(self, slug: str) -> AnalysisAreaSummary | None: ...

    async def list_children(self, slug: str) -> Sequence[AnalysisAreaSummary]: ...


__all__ = [
    "SERVICE_ID",
    "SERVICE_VERSION",
    "AnalysisAreaGeometry",
    "AnalysisAreaQueryService",
    "AnalysisAreaSummary",
]
