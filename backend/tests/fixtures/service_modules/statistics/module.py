from collections.abc import Sequence

from app.platform.modules.sdk import ModuleContext, ModuleDefinition, parse_manifest
from tests.fixtures.service_modules.analysis_areas.contracts import (
    SERVICE_ID,
    SERVICE_VERSION,
    AnalysisAreaQueryService,
    AnalysisAreaSummary,
)

MANIFEST = parse_manifest(
    {
        "manifest_version": 1,
        "id": "statistics-fixture",
        "name": "Statistics Service Consumer Fixture",
        "version": "1.0.0",
        "requires": {
            "host": ">=0.2.0,<1.0.0",
            "sdk": ">=1.3.0,<2.0.0",
            "modules": {"analysis-areas-fixture": ">=1.0.0,<2.0.0"},
        },
    }
)


class StatisticsFixtureModule:
    manifest = MANIFEST

    def __init__(self) -> None:
        self._areas: AnalysisAreaQueryService | None = None

    def register(self, context: ModuleContext) -> None:
        assert context.services is not None
        self._areas = context.services.require(
            AnalysisAreaQueryService,
            service_id=SERVICE_ID,
            version=SERVICE_VERSION,
        )

    async def areas(self) -> Sequence[AnalysisAreaSummary]:
        assert self._areas is not None
        return await self._areas.list_areas()


DEFINITION = ModuleDefinition(
    manifest=MANIFEST,
    loader=StatisticsFixtureModule,
    origin=__name__,
    declared_id=MANIFEST.id,
)
