"""Hostseitige Erzeugung modulgebundener öffentlicher SDK-Contexts."""

import logging
from collections.abc import Awaitable, Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.platform.modules.contracts import ModuleRegistrationContext
from app.platform.modules.jobs import JobRegistry
from app.platform.modules.manifest import ModuleManifestV1
from app.platform.modules.permissions import (
    PermissionEngine,
    PermissionSubject,
    RegistryPermissionPort,
)
from app.platform.modules.sdk import (
    OSM_SNAPSHOT_QUERY_SERVICE_ID,
    OSM_SNAPSHOT_QUERY_SERVICE_VERSION,
    POLYGON_ASSIGNMENT_SERVICE_ID,
    POLYGON_ASSIGNMENT_SERVICE_VERSION,
    CacheGenerationPort,
    CachePort,
    DatabaseSessionProvider,
    EventBusPort,
    HttpClientFactoryPort,
    MapPreviewPort,
    MetricsPort,
    ModuleContext,
    ModuleSettingsPort,
    ObservabilityPort,
    OsmSnapshotQueryPort,
    PermissionDependencyFactory,
    PermissionPort,
    PolygonAnalyticsPort,
    PolygonAssignmentPort,
    PolygonQueryPort,
    PublicQueryPort,
    SchedulerPort,
    ServiceRegistryPort,
    SpanPort,
    StatisticsQueryPort,
    StoragePort,
    TracerPort,
)
from app.platform.modules.services import ServiceRegistry
from app.platform.modules.settings import ModuleSettingsRegistry, read_module_environment

if TYPE_CHECKING:
    from app.platform.events.bus import InProcessEventBus


class _NoOpMetrics:
    def increment(
        self,
        name: str,
        *,
        value: float = 1,
        attributes: Mapping[str, str] | None = None,
    ) -> None:
        del name, value, attributes

    def observe(
        self,
        name: str,
        value: float,
        *,
        attributes: Mapping[str, str] | None = None,
    ) -> None:
        del name, value, attributes


class _NoOpSpan:
    def set_attribute(self, name: str, value: str | float | bool) -> None:
        del name, value

    def record_exception(self, error: Exception) -> None:
        del error


class _NoOpTracer:
    @contextmanager
    def span(
        self,
        name: str,
        *,
        attributes: Mapping[str, str] | None = None,
    ) -> Iterator[SpanPort]:
        del name, attributes
        yield _NoOpSpan()


@dataclass(frozen=True, slots=True)
class _ModuleObservability:
    logger: logging.LoggerAdapter
    metrics: MetricsPort
    tracer: TracerPort


@dataclass(frozen=True, slots=True)
class ModuleHostServices:
    """Hostseitiges Adapter-Bundle für öffentliche, typisierte Capabilities."""

    database: DatabaseSessionProvider | None = None
    events: EventBusPort | None = None
    services: ServiceRegistryPort | None = None
    permissions: PermissionPort | None = None
    permission_dependencies: PermissionDependencyFactory | None = None
    cache: CachePort | None = None
    cache_factory: Callable[[str], CachePort] | None = None
    cache_generations: CacheGenerationPort | None = None
    public_queries: PublicQueryPort | None = None
    map_previews: MapPreviewPort | None = None
    polygons: PolygonQueryPort | None = None
    polygon_analytics: PolygonAnalyticsPort | None = None
    polygon_assignments: PolygonAssignmentPort | None = None
    statistics: StatisticsQueryPort | None = None
    osm_snapshots: OsmSnapshotQueryPort | None = None
    storage: StoragePort | None = None
    http: HttpClientFactoryPort | None = None
    scheduler: SchedulerPort | None = None
    settings: ModuleSettingsPort | None = None


class ModuleContextFactory:
    """Erzeugt pro Manifest genau einen unveränderlichen ModuleContext."""

    def __init__(
        self,
        services: ModuleHostServices | None = None,
        *,
        event_bus: "InProcessEventBus | None" = None,
        settings_registry: ModuleSettingsRegistry | None = None,
        job_registry: JobRegistry | None = None,
        permission_engine: PermissionEngine | None = None,
        permission_subject_loader: Callable[
            [str], Awaitable[PermissionSubject | None]
        ]
        | None = None,
        module_environment: Mapping[str, str] | None = None,
        module_env_file: Path | None = None,
    ) -> None:
        self._services = services or ModuleHostServices()
        self._event_bus = event_bus
        self._service_registry: ServiceRegistry | None = None
        if self._services.services is None:
            self._service_registry = ServiceRegistry()
            if self._services.osm_snapshots is not None:
                self._service_registry.register(
                    provider_module="platform",
                    contract=OsmSnapshotQueryPort,
                    implementation=self._services.osm_snapshots,
                    service_id=OSM_SNAPSHOT_QUERY_SERVICE_ID,
                    version=OSM_SNAPSHOT_QUERY_SERVICE_VERSION,
                )
            if self._services.polygon_assignments is not None:
                self._service_registry.register(
                    provider_module="platform",
                    contract=PolygonAssignmentPort,
                    implementation=self._services.polygon_assignments,
                    service_id=POLYGON_ASSIGNMENT_SERVICE_ID,
                    version=POLYGON_ASSIGNMENT_SERVICE_VERSION,
                )
        self._settings_registry: ModuleSettingsRegistry | None = None
        if self._services.settings is None:
            self._settings_registry = settings_registry or ModuleSettingsRegistry(
                read_module_environment(
                    env_file=module_env_file,
                    environment=module_environment,
                )
            )
        self._job_registry: JobRegistry | None = None
        if self._services.scheduler is None:
            self._job_registry = job_registry or JobRegistry()
        self._permission_port: PermissionPort | None = self._services.permissions
        if (
            self._permission_port is None
            and permission_engine is not None
            and permission_subject_loader is not None
        ):
            self._permission_port = RegistryPermissionPort(
                permission_engine, permission_subject_loader
            )

    @property
    def service_registry(self) -> "ServiceRegistry | None":
        return self._service_registry

    @property
    def settings_registry(self) -> ModuleSettingsRegistry | None:
        return self._settings_registry

    @property
    def job_registry(self) -> JobRegistry | None:
        return self._job_registry

    def create(
        self,
        manifest: ModuleManifestV1,
        registration: ModuleRegistrationContext,
    ) -> ModuleContext:
        from app.platform.events.outbox import HostEventBusAdapter

        logger = logging.LoggerAdapter(
            logging.getLogger(f"app.modules.{manifest.id}"),
            {"module_id": manifest.id, "module_version": manifest.version},
        )
        observability: ObservabilityPort = _ModuleObservability(
            logger=logger,
            metrics=_NoOpMetrics(),
            tracer=_NoOpTracer(),
        )
        event_adapter = self._services.events
        if event_adapter is None and self._event_bus is not None:
            event_adapter = HostEventBusAdapter(self._event_bus, module_id=manifest.id)
        service_adapter = self._services.services
        if service_adapter is None and self._service_registry is not None:
            service_adapter = self._service_registry.bind(manifest)
        settings_adapter = self._services.settings
        if settings_adapter is None and self._settings_registry is not None:
            settings_adapter = self._settings_registry.bind(manifest)
        scheduler_adapter = self._services.scheduler
        if scheduler_adapter is None and self._job_registry is not None:
            scheduler_adapter = self._job_registry.bind(manifest)
        context = ModuleContext(
            module_id=manifest.id,
            module_version=manifest.version,
            api=registration,
            lifecycle=registration,
            observability=observability,
            database=self._services.database,
            events=event_adapter,
            services=service_adapter,
            permissions=self._permission_port,
            permission_dependencies=self._services.permission_dependencies,
            cache=(
                self._services.cache_factory(manifest.id)
                if self._services.cache_factory is not None
                else self._services.cache
            ),
            cache_generations=self._services.cache_generations,
            public_queries=self._services.public_queries,
            map_previews=self._services.map_previews,
            polygons=self._services.polygons,
            polygon_analytics=self._services.polygon_analytics,
            statistics=self._services.statistics,
            storage=self._services.storage,
            http=self._services.http,
            scheduler=scheduler_adapter,
            settings=settings_adapter,
        )
        if scheduler_adapter is not None and self._job_registry is not None:
            scheduler_adapter.attach_context(context)
        return context
