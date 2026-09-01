"""External-style consumer of only the public Polygon Spatial Match contract."""

from app.platform.modules.sdk import (
    POLYGON_SPATIAL_MATCH_SERVICE_ID,
    POLYGON_SPATIAL_MATCH_SERVICE_VERSION,
    ModuleContext,
    ModuleDefinition,
    ModuleManifestV1,
    PolygonSpatialMatchPort,
    PolygonSpatialMatchRequest,
    PolygonSpatialMatchResult,
    parse_manifest,
)

MANIFEST = parse_manifest(
    {
        "manifest_version": 1,
        "id": "test-polygon-spatial-match-consumer",
        "name": "Polygon spatial match contract test module",
        "version": "1.0.0",
        "requires": {"host": ">=0.2.0,<1.0.0", "sdk": ">=1.12.0,<2.0.0"},
    },
    origin="tests.fixtures.polygon_assignment_contract_module",
)


class PolygonSpatialMatchContractConsumerModule:
    manifest: ModuleManifestV1 = MANIFEST

    def register(self, context: ModuleContext) -> None:
        if context.services is None:
            raise RuntimeError("The service registry is required.")
        self.spatial_matches = context.services.require(
            PolygonSpatialMatchPort,
            service_id=POLYGON_SPATIAL_MATCH_SERVICE_ID,
            version=POLYGON_SPATIAL_MATCH_SERVICE_VERSION,
        )

    async def match(
        self, session, request: PolygonSpatialMatchRequest
    ) -> PolygonSpatialMatchResult:
        return await self.spatial_matches.match_polygons(session, request)


DEFINITION = ModuleDefinition(
    manifest=MANIFEST,
    loader=PolygonSpatialMatchContractConsumerModule,
    origin="tests.fixtures.polygon_assignment_contract_module",
    declared_id=MANIFEST.id,
)
