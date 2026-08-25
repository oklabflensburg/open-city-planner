"""Hostseitige Erzeugung modulgebundener öffentlicher SDK-Contexts."""

import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass

from app.platform.modules.contracts import ModuleRegistrationContext
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

    def __init__(self, services: ModuleHostServices | None = None) -> None:
        self._services = services or ModuleHostServices()

    def create(
        self,
        manifest: ModuleManifestV1,
        registration: ModuleRegistrationContext,
    ) -> ModuleContext:
        logger = logging.LoggerAdapter(
            logging.getLogger(f"app.modules.{manifest.id}"),
            {"module_id": manifest.id, "module_version": manifest.version},
        )
        observability: ObservabilityPort = _ModuleObservability(
            logger=logger,
            metrics=_NoOpMetrics(),
            tracer=_NoOpTracer(),
        )
        return ModuleContext(
            module_id=manifest.id,
            module_version=manifest.version,
            api=registration,
            lifecycle=registration,
            observability=observability,
            database=self._services.database,
            events=self._services.events,
            services=self._services.services,
            permissions=self._services.permissions,
            cache=self._services.cache,
            storage=self._services.storage,
            http=self._services.http,
            scheduler=self._services.scheduler,
            settings=self._services.settings,
        )
