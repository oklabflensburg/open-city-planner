"""Referenzmodul für Subscriber-Registrierung ausschließlich über das Public SDK."""

from app.platform.modules.sdk import (
    EventEnvelope,
    ModuleContext,
    ModuleDefinition,
    ModuleManifestV1,
    parse_manifest,
)

MANIFEST = parse_manifest(
    {
        "manifest_version": 1,
        "id": "test-event-subscriber",
        "name": "Event subscriber test module",
        "version": "1.0.0",
        "requires": {"host": ">=0.2.0,<1.0.0", "sdk": ">=1.1.0,<2.0.0"},
    },
    origin="tests.fixtures.event_subscriber_module",
)


class EventSubscriberModule:
    manifest: ModuleManifestV1 = MANIFEST

    def register(self, context: ModuleContext) -> None:
        if context.events is None:
            raise RuntimeError("The event port is required by this module.")
        context.events.subscribe(
            "example.created",
            handler_id="test-event-subscriber.example-created",
            versions=frozenset({1}),
            handler=self.handle,
        )

    async def handle(self, _event: EventEnvelope) -> None:
        return None


DEFINITION = ModuleDefinition(
    manifest=MANIFEST,
    loader=EventSubscriberModule,
    origin="tests.fixtures.event_subscriber_module",
    declared_id=MANIFEST.id,
)
