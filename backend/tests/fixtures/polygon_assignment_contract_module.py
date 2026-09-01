"""External-style consumer of only the public Polygon Assignment SDK contract."""

from app.platform.modules.sdk import (
    POLYGON_ASSIGNMENT_SERVICE_ID,
    POLYGON_ASSIGNMENT_SERVICE_VERSION,
    ModuleContext,
    ModuleDefinition,
    ModuleManifestV1,
    PolygonAssignmentPort,
    PolygonAssignmentRequest,
    PolygonAssignmentResult,
    parse_manifest,
)

MANIFEST = parse_manifest(
    {
        "manifest_version": 1,
        "id": "test-polygon-assignment-consumer",
        "name": "Polygon assignment contract test module",
        "version": "1.0.0",
        "requires": {"host": ">=0.2.0,<1.0.0", "sdk": ">=1.12.0,<2.0.0"},
    },
    origin="tests.fixtures.polygon_assignment_contract_module",
)


class PolygonAssignmentContractConsumerModule:
    manifest: ModuleManifestV1 = MANIFEST

    def register(self, context: ModuleContext) -> None:
        if context.services is None:
            raise RuntimeError("The service registry is required.")
        self.assignments = context.services.require(
            PolygonAssignmentPort,
            service_id=POLYGON_ASSIGNMENT_SERVICE_ID,
            version=POLYGON_ASSIGNMENT_SERVICE_VERSION,
        )

    async def refresh(
        self, session, request: PolygonAssignmentRequest
    ) -> PolygonAssignmentResult:
        return await self.assignments.refresh_assignments(session, request)


DEFINITION = ModuleDefinition(
    manifest=MANIFEST,
    loader=PolygonAssignmentContractConsumerModule,
    origin="tests.fixtures.polygon_assignment_contract_module",
    declared_id=MANIFEST.id,
)
