"""Composition Root des ausführbaren Referenzmoduls."""

from app.platform.modules.sdk import (
    EventEnvelope,
    JobDefinition,
    JobSchedule,
    ModuleContext,
    ModuleDefinition,
    ModuleMigrationSource,
    ModulePersistenceContribution,
    ModuleSettingsContribution,
    parse_manifest,
)

from .api import create_router
from .application import ReferenceItemService
from .persistence import METADATA
from .settings import ReferenceSettings

MANIFEST = parse_manifest(
    {
        "manifest_version": 1,
        "id": "reference",
        "name": "Reference Notes",
        "version": "1.0.0",
        "requires": {"host": ">=0.2.0,<1.0.0", "sdk": ">=1.7.0,<2.0.0"},
        "backend": {"package": "open-city-map-backend"},
        "frontend": {"package": "reference"},
        "capabilities": ["reference.items", "reference.map-layer"],
        "permissions": ["reference.items-write"],
        "config": {"namespace": "reference"},
        "persistence": {"schema": "reference", "migrations": True},
    },
    origin=__name__,
)


class ReferenceModule:
    manifest = MANIFEST

    def register(self, context: ModuleContext) -> None:
        if context.permission_dependencies is None:
            raise RuntimeError("The reference module requires request permission dependencies.")
        service = ReferenceItemService(context)
        context.api.include_router(
            create_router(service, context.permission_dependencies),
            prefix="/api/v1/modules/reference",
            tags=("Reference module",),
        )

        if context.events is None:
            raise RuntimeError("The reference module requires the event port.")

        async def observe_created(event: EventEnvelope) -> None:
            context.observability.metrics.increment("items-created")
            context.logger.info("Reference item event handled", extra={"event_id": str(event.event_id)})

        context.events.subscribe(
            "reference.item-created",
            handler_id="reference.observe-item-created",
            versions=frozenset({1}),
            handler=observe_created,
        )

        if context.scheduler is None:
            raise RuntimeError("The reference module requires the scheduler port.")
        settings = context.settings.require(ReferenceSettings) if context.settings else ReferenceSettings()

        async def count_items(_context: ModuleContext) -> int:
            count = await service.count_items()
            context.observability.metrics.observe("items-total", float(count))
            return count

        context.scheduler.register(
            JobDefinition(
                job_id="count-items",
                handler=count_items,
                schedule=JobSchedule(interval_seconds=settings.job_interval_seconds),
                timeout_seconds=30,
            )
        )


DEFINITION = ModuleDefinition(
    manifest=MANIFEST,
    loader=ReferenceModule,
    origin=__name__,
    declared_id=MANIFEST.id,
    persistence=ModulePersistenceContribution(
        module_id=MANIFEST.id,
        metadata=METADATA,
        schema="reference",
        migration_source=ModuleMigrationSource(
            package="app.modules.reference.persistence",
            resource="migrations",
            revision_namespace="mod_reference",
        ),
    ),
    settings=ModuleSettingsContribution(
        module_id=MANIFEST.id,
        namespace="reference",
        model=ReferenceSettings,
    ),
)
