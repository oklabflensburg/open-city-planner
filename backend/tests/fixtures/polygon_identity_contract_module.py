"""External-style consumer chaining public polygon matching and identity contracts."""

from uuid import UUID

from app.platform.modules.sdk import (
    POLYGON_IDENTITY_SERVICE_ID,
    POLYGON_IDENTITY_SERVICE_VERSION,
    POLYGON_SPATIAL_MATCH_SERVICE_ID,
    POLYGON_SPATIAL_MATCH_SERVICE_VERSION,
    ModuleContext,
    ModuleDefinition,
    ModuleManifestV1,
    PolygonIdentityPort,
    PolygonIdentityRequest,
    PolygonIdentityResult,
    PolygonSpatialMatchPort,
    PolygonSpatialMatchRequest,
    parse_manifest,
)

MANIFEST = parse_manifest(
    {
        "manifest_version": 1,
        "id": "test-polygon-identity-consumer",
        "name": "Polygon identity contract test module",
        "version": "1.0.0",
        "requires": {"host": ">=0.2.0,<1.0.0", "sdk": ">=1.13.0,<2.0.0"},
    },
    origin="tests.fixtures.polygon_identity_contract_module",
)


class PolygonIdentityContractConsumerModule:
    manifest: ModuleManifestV1 = MANIFEST

    def register(self, context: ModuleContext) -> None:
        if context.services is None:
            raise RuntimeError("The service registry is required.")
        self.spatial_matches = context.services.require(
            PolygonSpatialMatchPort,
            service_id=POLYGON_SPATIAL_MATCH_SERVICE_ID,
            version=POLYGON_SPATIAL_MATCH_SERVICE_VERSION,
        )
        self.polygon_identities = context.services.require(
            PolygonIdentityPort,
            service_id=POLYGON_IDENTITY_SERVICE_ID,
            version=POLYGON_IDENTITY_SERVICE_VERSION,
        )

    async def resolve_matches(
        self, session, request: PolygonSpatialMatchRequest
    ) -> PolygonIdentityResult:
        matches = await self.spatial_matches.match_polygons(session, request)
        identity_request = PolygonIdentityRequest(
            tuple(UUID(match.polygon_id) for match in matches.matches)
        )
        return await self.polygon_identities.resolve(session, identity_request)


DEFINITION = ModuleDefinition(
    manifest=MANIFEST,
    loader=PolygonIdentityContractConsumerModule,
    origin="tests.fixtures.polygon_identity_contract_module",
    declared_id=MANIFEST.id,
)
