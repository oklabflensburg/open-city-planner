"""Öffentliches Backend-SDK für Open-City-Planner-Module.

Dieses Modul ist der stabile Importpfad für Modulcode. Es definiert ausschließlich
Plattform-Ports und importiert keine Host-Infrastruktur oder Fachdomänen.
"""

import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from dataclasses import dataclass
from typing import Protocol, TypeVar

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.modules.manifest import (
    ManifestInput,
    ModuleManifestV1,
    parse_manifest,
)

type ModuleLifecycleHook = Callable[[], Awaitable[None]]
type ModuleLoader = Callable[[], "BackendModule"]
type JobHandler = Callable[[], Awaitable[None]]
T = TypeVar("T")


class ApiRegistrar(Protocol):
    """Registriert vom Host kontrolliert einzubindende FastAPI-Router."""

    def include_router(
        self,
        router: APIRouter,
        *,
        prefix: str = "",
        tags: Sequence[str] = (),
    ) -> None: ...


class LifecycleRegistrar(Protocol):
    """Registriert asynchrone Hooks ohne externe Side Effects während register()."""

    def add_lifecycle(
        self,
        *,
        startup: ModuleLifecycleHook | None = None,
        shutdown: ModuleLifecycleHook | None = None,
    ) -> None: ...


class DatabaseSessionProvider(Protocol):
    """Öffnet eine vom Host verwaltete SQLAlchemy-Session."""

    def session(self) -> AbstractAsyncContextManager[AsyncSession]: ...


class DomainEvent(Protocol):
    """Minimale Identität eines vom Fachmodul definierten Domain Events."""

    event_type: str
    event_version: int


class EventBusPort(Protocol):
    """Publiziert Domain Events; Zustellung und Outbox folgen in #96."""

    async def publish(self, event: DomainEvent) -> None: ...


class ServiceRegistryPort(Protocol):
    """Löst ausschließlich explizite öffentliche Cross-Module-Contracts auf."""

    def resolve(self, contract: type[T]) -> T: ...


class PermissionPort(Protocol):
    """Prüft eine stabile Permission-ID; die Policy Engine folgt in #104."""

    async def is_allowed(
        self,
        permission_id: str,
        *,
        principal_id: str | None,
        resource_id: str | None = None,
    ) -> bool: ...


class CachePort(Protocol):
    """Modulgebundener Byte-Cache mit TTL in positiven ganzen Sekunden."""

    async def get(self, key: str) -> bytes | None: ...

    async def set(self, key: str, value: bytes, *, ttl_seconds: int) -> bool: ...

    async def delete(self, *keys: str) -> int: ...

    async def clear(self) -> int: ...


class MetricsPort(Protocol):
    """Vendor-neutraler Zugriff auf begrenzte Modulmetriken."""

    def increment(
        self,
        name: str,
        *,
        value: float = 1,
        attributes: Mapping[str, str] | None = None,
    ) -> None: ...

    def observe(
        self,
        name: str,
        value: float,
        *,
        attributes: Mapping[str, str] | None = None,
    ) -> None: ...


class SpanPort(Protocol):
    """Kleiner, vendor-neutraler Trace-Span."""

    def set_attribute(self, name: str, value: str | float | bool) -> None: ...

    def record_exception(self, error: Exception) -> None: ...


class TracerPort(Protocol):
    """Erzeugt automatisch modulgebundene Trace-Spans."""

    def span(
        self,
        name: str,
        *,
        attributes: Mapping[str, str] | None = None,
    ) -> AbstractContextManager[SpanPort]: ...


class ObservabilityPort(Protocol):
    """Gebündelte, bereits an Modul-ID und Modulversion gebundene Telemetrie."""

    @property
    def logger(self) -> logging.LoggerAdapter: ...

    @property
    def metrics(self) -> MetricsPort: ...

    @property
    def tracer(self) -> TracerPort: ...


class StoragePort(Protocol):
    """Modulgebundener Blob-Storage ohne Dateisystem- oder Cloud-Annahmen."""

    async def read(self, key: str) -> bytes | None: ...

    async def write(self, key: str, value: bytes, *, content_type: str | None = None) -> None: ...

    async def delete(self, key: str) -> bool: ...

    async def exists(self, key: str) -> bool: ...


class HttpResponsePort(Protocol):
    """Begrenzte HTTP-Antwort ohne Zugriff auf den konkreten Client."""

    status_code: int
    headers: Mapping[str, str]
    content: bytes

    def json(self) -> object: ...


class HttpClientPort(Protocol):
    """Asynchroner HTTP-Port mit Host-kontrollierten Transport-Policies."""

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        content: bytes | None = None,
    ) -> HttpResponsePort: ...


class HttpClientFactoryPort(Protocol):
    """Erzeugt einen sicheren Client; Timeouts und User-Agent besitzt der Host."""

    def create(
        self,
        *,
        service_name: str,
        base_url: str | None = None,
    ) -> AbstractAsyncContextManager[HttpClientPort]: ...


class SchedulerPort(Protocol):
    """Registriert modulgebundene Jobs; Ausführung und Scheduling folgen in #100."""

    def register(self, job_id: str, handler: JobHandler) -> None: ...


class ModuleSettingsPort(Protocol):
    """Liest ausschließlich Werte aus dem Namespace des aktuellen Moduls."""

    def get(self, key: str, default: T | None = None) -> object | T | None: ...

    def require(self, key: str) -> object: ...


@dataclass(frozen=True, slots=True)
class ModuleContext:
    """Unveränderlicher, an genau ein Modul gebundener Host-Service-Context."""

    module_id: str
    module_version: str
    api: ApiRegistrar
    lifecycle: LifecycleRegistrar
    observability: ObservabilityPort
    database: DatabaseSessionProvider | None = None
    events: EventBusPort | None = None
    services: ServiceRegistryPort | None = None
    permissions: PermissionPort | None = None
    cache: CachePort | None = None
    storage: StoragePort | None = None
    http: HttpClientFactoryPort | None = None
    scheduler: SchedulerPort | None = None
    settings: ModuleSettingsPort | None = None

    @property
    def logger(self) -> logging.LoggerAdapter:
        return self.observability.logger

    # Kompatibilitäts-Proxys für den kleinen Registration Context aus #94.
    def include_router(
        self,
        router: APIRouter,
        *,
        prefix: str = "",
        tags: Sequence[str] = (),
    ) -> None:
        self.api.include_router(router, prefix=prefix, tags=tags)

    def add_lifecycle(
        self,
        *,
        startup: ModuleLifecycleHook | None = None,
        shutdown: ModuleLifecycleHook | None = None,
    ) -> None:
        self.lifecycle.add_lifecycle(startup=startup, shutdown=shutdown)


class BackendModule(Protocol):
    """Öffentlicher Backend-Modulvertrag."""

    manifest: ModuleManifestV1

    def register(self, context: ModuleContext) -> None: ...


@dataclass(frozen=True, slots=True)
class ModuleDefinition:
    """Passive Discovery-Metadaten und verzögerte Modulinstanziierung."""

    manifest: ManifestInput | ModuleManifestV1
    loader: ModuleLoader
    origin: str
    declared_id: str


__all__ = [
    "ApiRegistrar",
    "BackendModule",
    "CachePort",
    "DatabaseSessionProvider",
    "DomainEvent",
    "EventBusPort",
    "HttpClientFactoryPort",
    "HttpClientPort",
    "HttpResponsePort",
    "JobHandler",
    "LifecycleRegistrar",
    "MetricsPort",
    "ModuleContext",
    "ModuleDefinition",
    "ModuleLifecycleHook",
    "ModuleManifestV1",
    "ModuleSettingsPort",
    "ObservabilityPort",
    "PermissionPort",
    "SchedulerPort",
    "ServiceRegistryPort",
    "SpanPort",
    "StoragePort",
    "TracerPort",
    "parse_manifest",
]
