"""External-style consumer of only the public OSM SDK contract."""

from app.platform.modules.sdk import (
    OSM_POSTPROCESSING_COMPLETED_EVENT,
    OSM_POSTPROCESSING_COMPLETED_EVENT_VERSION,
    OSM_SNAPSHOT_QUERY_SERVICE_ID,
    OSM_SNAPSHOT_QUERY_SERVICE_VERSION,
    EventEnvelope,
    ModuleContext,
    ModuleDefinition,
    ModuleManifestV1,
    OsmFeatureSnapshotPage,
    OsmSnapshotQuery,
    OsmSnapshotQueryPort,
    parse_manifest,
)

MANIFEST = parse_manifest(
    {
        "manifest_version": 1,
        "id": "test-osm-contract-consumer",
        "name": "OSM contract consumer test module",
        "version": "1.0.0",
        "requires": {"host": ">=0.2.0,<1.0.0", "sdk": ">=1.11.0,<2.0.0"},
    },
    origin="tests.fixtures.osm_contract_module",
)


class OsmContractConsumerModule:
    manifest: ModuleManifestV1 = MANIFEST

    def register(self, context: ModuleContext) -> None:
        if context.services is None or context.events is None:
            raise RuntimeError("The service registry and event bus are required.")
        self.snapshots = context.services.require(
            OsmSnapshotQueryPort,
            service_id=OSM_SNAPSHOT_QUERY_SERVICE_ID,
            version=OSM_SNAPSHOT_QUERY_SERVICE_VERSION,
        )
        context.events.subscribe(
            OSM_POSTPROCESSING_COMPLETED_EVENT,
            handler_id="test-osm-contract-consumer.postprocessing-completed",
            versions=frozenset({OSM_POSTPROCESSING_COMPLETED_EVENT_VERSION}),
            handler=self.handle,
        )

    async def handle(self, _event: EventEnvelope) -> None:
        return None

    async def list_snapshots(
        self, session, query: OsmSnapshotQuery
    ) -> OsmFeatureSnapshotPage:
        """Read snapshots solely through the public service resolved at registration."""

        return await self.snapshots.list_features(session, query)


DEFINITION = ModuleDefinition(
    manifest=MANIFEST,
    loader=OsmContractConsumerModule,
    origin="tests.fixtures.osm_contract_module",
    declared_id=MANIFEST.id,
)
