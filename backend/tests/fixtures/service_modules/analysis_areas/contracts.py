"""Einziger modulübergreifend importierbarer Namespace des Provider-Fixtures."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.platform.modules.sdk import JsonValue

SERVICE_ID = "analysis-areas-fixture.query"
SERVICE_VERSION = 1


@dataclass(frozen=True, slots=True)
class AnalysisAreaSummary:
    area_id: str
    name: str
    geometry: Mapping[str, JsonValue]


class AnalysisAreaQueryService(Protocol):
    async def list_areas(self) -> Sequence[AnalysisAreaSummary]: ...
