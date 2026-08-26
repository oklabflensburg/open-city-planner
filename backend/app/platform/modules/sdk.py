"""Öffentliches Backend-SDK für Open-City-Planner-Module.

Dieses Modul ist der stabile Importpfad für Modulcode. Es definiert ausschließlich
Plattform-Ports und importiert keine Host-Infrastruktur oder Fachdomänen.
"""

import logging
import math
import posixpath
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Protocol, TypeVar
from uuid import UUID, uuid4

from fastapi import APIRouter
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.modules.manifest import (
    ManifestInput,
    ModuleManifestV1,
    parse_manifest,
)

type ModuleLifecycleHook = Callable[[], Awaitable[None]]
type ModuleLoader = Callable[[], "BackendModule"]
type JobHandler = Callable[[], Awaitable[None]]
type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list["JsonValue"] | Mapping[str, "JsonValue"]
T = TypeVar("T")
_EVENT_NAME = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+$")
_REVISION_NAMESPACE = re.compile(r"^mod_[a-z][a-z0-9_]*$")
_PYTHON_IMPORT_PACKAGE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")


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


@dataclass(frozen=True, slots=True)
class ModuleMigrationSource:
    """Installierte, lokale Alembic-Quelle eines Moduls."""

    package: str
    resource: str
    revision_namespace: str

    def __post_init__(self) -> None:
        if not _PYTHON_IMPORT_PACKAGE.fullmatch(self.package):
            raise ValueError("Migration packages must be installed Python package names.")
        normalized = posixpath.normpath(self.resource)
        if (
            not self.resource
            or self.resource.startswith(("/", "\\"))
            or normalized in {".", ".."}
            or normalized.startswith("../")
            or "://" in self.resource
            or "\\" in self.resource
        ):
            raise ValueError("Migration resources must be relative installed-package paths.")
        if not _REVISION_NAMESPACE.fullmatch(self.revision_namespace):
            raise ValueError('Revision namespaces must use the form "mod_<module_id>".')


@dataclass(frozen=True, slots=True)
class ModulePersistenceContribution:
    """Passive ORM- und Migrationsmetadaten einer ModuleDefinition."""

    module_id: str
    metadata: MetaData
    schema: str
    migration_source: ModuleMigrationSource | None = None


class DomainEvent(Protocol):
    """Kompatible minimale Event-Identität aus SDK 1.0."""

    event_type: str
    event_version: int


class SerializableDomainEvent(Protocol):
    """Vom Producer besessener, stark typisierbarer Event-Payload-Contract."""

    event_name: str
    event_version: int

    def to_payload(self) -> Mapping[str, JsonValue]: ...


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """Fachneutraler, persistierbarer Event-Envelope mit stabiler Identität."""

    event_id: UUID
    event_name: str
    event_version: int
    occurred_at: datetime
    payload: Mapping[str, JsonValue]
    correlation_id: str | None = None
    causation_id: str | None = None
    trace_context: Mapping[str, str] = MappingProxyType({})
    producer_module: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, UUID):
            raise TypeError("Event IDs must be UUID values.")
        if not isinstance(self.event_name, str) or not _EVENT_NAME.fullmatch(self.event_name):
            raise ValueError("Event names must use the form <module-id>.<event-name>.")
        if len(self.event_name) > 160:
            raise ValueError("Event names must not exceed 160 characters.")
        if type(self.event_version) is not int or self.event_version < 1:
            raise ValueError("Event versions must be positive integers.")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("Event timestamps must include a timezone.")
        if self.occurred_at.utcoffset() != UTC.utcoffset(self.occurred_at):
            raise ValueError("Event timestamps must use UTC.")
        if not isinstance(self.payload, Mapping):
            raise TypeError("Event payloads must be JSON objects.")
        _validate_json_value(self.payload, path="payload")
        _validate_string_mapping(self.trace_context, name="trace_context")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))
        object.__setattr__(self, "trace_context", MappingProxyType(dict(self.trace_context)))


type EventHandler = Callable[[EventEnvelope], Awaitable[None] | None]


def event_envelope(
    event: DomainEvent | SerializableDomainEvent,
    *,
    event_id: UUID | None = None,
    occurred_at: datetime | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    trace_context: Mapping[str, str] | None = None,
) -> EventEnvelope:
    """Erzeuge Metadaten für ein fachlich typisiertes Event ohne implizite Serialisierung."""

    event_name = getattr(event, "event_name", None) or event.event_type
    serializer = getattr(event, "to_payload", None)
    payload = serializer() if serializer is not None else {}
    return EventEnvelope(
        event_id=event_id or uuid4(),
        event_name=event_name,
        event_version=event.event_version,
        occurred_at=occurred_at or datetime.now(UTC),
        payload=payload,
        correlation_id=correlation_id,
        causation_id=causation_id,
        trace_context=trace_context or {},
    )


def _validate_json_value(value: object, *, path: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{path} contains a non-finite number.")
    if value is None or isinstance(value, str | bool | int | float):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, path=f"{path}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} contains a non-string object key.")
            _validate_json_value(item, path=f"{path}.{key}")
        return
    raise TypeError(f"{path} contains the non-JSON value {type(value).__name__}.")


def _validate_string_mapping(value: Mapping[object, object], *, name: str) -> None:
    if not all(isinstance(key, str) and isinstance(item, str) for key, item in value.items()):
        raise TypeError(f"{name} must contain only string keys and values.")


class EventBusPort(Protocol):
    """Publiziert Events direkt oder atomar über die transaktionale Outbox."""

    async def publish(
        self, event: DomainEvent | SerializableDomainEvent | EventEnvelope
    ) -> None: ...

    async def publish_after_commit(
        self,
        event: DomainEvent | SerializableDomainEvent | EventEnvelope,
        *,
        session: AsyncSession,
    ) -> EventEnvelope: ...

    def subscribe(
        self,
        event_name: str,
        *,
        handler_id: str,
        versions: frozenset[int],
        handler: EventHandler,
    ) -> None: ...


class ServiceRegistryPort(Protocol):
    """Registriert und löst explizite öffentliche Cross-Module-Contracts auf."""

    def register(
        self,
        contract: type[T],
        implementation: T,
        *,
        service_id: str,
        version: int,
        deprecated_since: str | None = None,
        replacement: str | None = None,
    ) -> None: ...

    def require(self, contract: type[T], *, service_id: str, version: int) -> T: ...

    def optional(self, contract: type[T], *, service_id: str, version: int) -> T | None: ...

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
    persistence: ModulePersistenceContribution | None = None


__all__ = [
    "ApiRegistrar",
    "BackendModule",
    "CachePort",
    "DatabaseSessionProvider",
    "DomainEvent",
    "EventBusPort",
    "EventEnvelope",
    "EventHandler",
    "HttpClientFactoryPort",
    "HttpClientPort",
    "HttpResponsePort",
    "JobHandler",
    "JsonScalar",
    "JsonValue",
    "LifecycleRegistrar",
    "MetricsPort",
    "ModuleContext",
    "ModuleDefinition",
    "ModuleLifecycleHook",
    "ModuleManifestV1",
    "ModuleMigrationSource",
    "ModulePersistenceContribution",
    "ModuleSettingsPort",
    "ObservabilityPort",
    "PermissionPort",
    "SchedulerPort",
    "SerializableDomainEvent",
    "ServiceRegistryPort",
    "SpanPort",
    "StoragePort",
    "TracerPort",
    "event_envelope",
    "parse_manifest",
]
