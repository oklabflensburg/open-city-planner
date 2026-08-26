from app.platform.modules.sdk import ModuleContext, ModuleDefinition, parse_manifest
from tests.fixtures.service_modules.analysis_areas.application import (
    InMemoryAnalysisAreaQueryService,
)
from tests.fixtures.service_modules.analysis_areas.contracts import (
    SERVICE_ID,
    SERVICE_VERSION,
    AnalysisAreaQueryService,
)

MANIFEST = parse_manifest(
    {
        "manifest_version": 1,
        "id": "analysis-areas-fixture",
        "name": "Analysis Areas Service Fixture",
        "version": "1.0.0",
        "requires": {"host": ">=0.2.0,<1.0.0", "sdk": ">=1.3.0,<2.0.0"},
    }
)


class AnalysisAreasFixtureModule:
    manifest = MANIFEST

    def register(self, context: ModuleContext) -> None:
        assert context.services is not None
        context.services.register(
            AnalysisAreaQueryService,
            InMemoryAnalysisAreaQueryService(),
            service_id=SERVICE_ID,
            version=SERVICE_VERSION,
        )


DEFINITION = ModuleDefinition(
    manifest=MANIFEST,
    loader=AnalysisAreasFixtureModule,
    origin=__name__,
    declared_id=MANIFEST.id,
)
