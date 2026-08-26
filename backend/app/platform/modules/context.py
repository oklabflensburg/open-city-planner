"""Hostseitige Erzeugung modulgebundener öffentlicher SDK-Contexts."""

import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.platform.modules.contracts import ModuleRegistrationContext
from app.platform.modules.jobs import JobRegistry
from app.platform.modules.manifest import ModuleManifestV1
from app.platform.modules.sdk import (
    CachePort,
    DatabaseSessionProvider,
    EventBusPort,
    HttpClientFactoryPort,
    MetricsPort,
    ModuleContext,
    ModuleSettingsPort,
    ObservabilityPort,
    PermissionPort,
    SchedulerPort,
    ServiceRegistryPort,
    SpanPort,
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
    """Hostseitiges Adapter-Bundle; optionale Ports folgen in ihren Folge-Issues."""

    database: DatabaseSessionProvider | None = None
    events: EventBusPort | None = None
    services: ServiceRegistryPort | None = None
    permissions: PermissionPort | None = None
    cache: CachePort | None = None
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
        module_environment: Mapping[str, str] | None = None,
        module_env_file: Path | None = None,
    ) -> None:
        self._services = services or ModuleHostServices()
        self._event_bus = event_bus
        self._service_registry: ServiceRegistry | None = None
        if self._services.services is None:
            self._service_registry = ServiceRegistry()
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
            permissions=self._services.permissions,
            cache=self._services.cache,
            storage=self._services.storage,
            http=self._services.http,
            scheduler=scheduler_adapter,
            settings=settings_adapter,
        )
        if scheduler_adapter is not None and self._job_registry is not None:
            scheduler_adapter.attach_context(context)
        return context
