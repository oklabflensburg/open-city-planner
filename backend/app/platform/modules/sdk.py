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
from typing import Protocol, TypeVar, overload
from uuid import UUID, uuid4

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.modules.manifest import (
    ManifestInput,
    ModuleManifestV1,
    parse_manifest,
)

type ModuleLifecycleHook = Callable[[], Awaitable[None]]
type ModuleLoader = Callable[[], "BackendModule"]
type JobHandler = Callable[["ModuleContext"], Awaitable[object | None]]
type LegacyJobHandler = Callable[[], Awaitable[object | None]]
type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list["JsonValue"] | Mapping[str, "JsonValue"]
T = TypeVar("T")
TSettings = TypeVar("TSettings", bound=BaseModel)
_EVENT_NAME = re.compile(r"^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+$")
_JOB_NAME = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
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
    adopted_revisions: frozenset[str] = frozenset()

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
        if not isinstance(self.adopted_revisions, frozenset):
            raise TypeError("Adopted migration revisions must be an immutable frozenset.")
        if any(
            not isinstance(revision, str)
            or not revision
            or revision != revision.strip()
            for revision in self.adopted_revisions
        ):
            raise ValueError("Adopted migration revisions must be non-empty exact IDs.")


@dataclass(frozen=True, slots=True)
class ModulePersistenceContribution:
    """Passive ORM- und Migrationsmetadaten einer ModuleDefinition."""

    module_id: str
    metadata: MetaData
    schema: str
    migration_source: ModuleMigrationSource | None = None
    adopted_tables: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        for table_name in self.adopted_tables:
            if not re.fullmatch(r"[a-z_][a-z0-9_]*", table_name):
                raise ValueError("Adopted table names must be unqualified PostgreSQL identifiers.")


@dataclass(frozen=True, slots=True)
class ModuleSettingsContribution:
    """Passives, vom Modul besessenes Schema für dessen namespacete Konfiguration."""

    module_id: str
    namespace: str
    model: type[BaseModel]


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


@dataclass(frozen=True, slots=True)
class PermissionDefinition:
    """Module-owned metadata for one stable permission ID."""

    id: str
    module_id: str
    description: str
    category: str | None = None
    deprecated: bool = False
    replacement: str | None = None


class PermissionPort(Protocol):
    """Prüft eine stabile Permission-ID über die hostseitige Policy Engine."""

    async def is_allowed(
        self,
        permission_id: str,
        *,
        principal_id: str | None,
        resource_id: str | None = None,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class ModulePrincipal:
    """Minimale, fachneutrale Identität einer authentifizierten Request-Person."""

    id: str


type ModulePrincipalDependency = Callable[..., Awaitable[ModulePrincipal]]


class PermissionDependencyFactory(Protocol):
    """Erzeugt Host-authentifizierte FastAPI-Dependencies für Modulrouten."""

    def require(
        self,
        permission_id: str,
        *,
        csrf: bool = False,
    ) -> ModulePrincipalDependency: ...


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


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Kleine, deterministische Retry-Policy für einen Joblauf."""

    max_attempts: int = 1
    initial_delay_seconds: float = 0
    backoff_multiplier: float = 2
    max_delay_seconds: float = 300

    def __post_init__(self) -> None:
        values = (
            self.initial_delay_seconds,
            self.backoff_multiplier,
            self.max_delay_seconds,
        )
        if type(self.max_attempts) is not int or self.max_attempts < 1:
            raise ValueError("Job retry max_attempts must be a positive integer.")
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
            raise ValueError("Job retry delays and multiplier must be finite numbers.")
        if self.initial_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("Job retry delays must not be negative.")
        if self.backoff_multiplier < 1:
            raise ValueError("Job retry backoff_multiplier must be at least one.")

    def delay_after(self, attempt: int) -> float:
        if type(attempt) is not int or attempt < 1:
            raise ValueError("Job retry attempts must be positive integers.")
        try:
            delay = self.initial_delay_seconds * self.backoff_multiplier ** (attempt - 1)
        except OverflowError:
            return self.max_delay_seconds
        return min(delay, self.max_delay_seconds)


@dataclass(frozen=True, slots=True)
class JobSchedule:
    """Technologieunabhängige V1-Anforderung für ein Ausführungsintervall."""

    interval_seconds: int

    def __post_init__(self) -> None:
        if type(self.interval_seconds) is not int or self.interval_seconds < 1:
            raise ValueError("Job schedule intervals must be positive integer seconds.")


@dataclass(frozen=True, slots=True)
class JobDefinition:
    """Öffentlicher, stabiler Job-Contract eines Moduls."""

    job_id: str
    handler: JobHandler
    retry: RetryPolicy = RetryPolicy()
    timeout_seconds: float | None = None
    schedule: JobSchedule | None = None
    allow_concurrent_runs: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.retry, RetryPolicy):
            raise TypeError("Job retry must be a RetryPolicy.")
        if self.schedule is not None and not isinstance(self.schedule, JobSchedule):
            raise TypeError("Job schedule must be a JobSchedule.")
        if (
            not (_JOB_NAME.fullmatch(self.job_id) or _EVENT_NAME.fullmatch(self.job_id))
            or len(self.job_id) > 160
        ):
            raise ValueError(
                "Jobs must use a local job name or the form <module-id>.<job-name>."
            )
        if not callable(self.handler):
            raise TypeError("Job handlers must be callable.")
        if self.timeout_seconds is not None and (
            type(self.timeout_seconds) not in (int, float)
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("Job timeouts must be positive finite seconds.")
        if type(self.allow_concurrent_runs) is not bool:
            raise TypeError("allow_concurrent_runs must be a boolean.")


class SchedulerPort(Protocol):
    """Registriert Jobs ausschließlich im Namespace des gebundenen Moduls."""

    @overload
    def register(self, definition: JobDefinition) -> None: ...

    @overload
    def register(self, job_id: str, handler: LegacyJobHandler) -> None: ...


class ModuleSettingsPort(Protocol):
    """Liefert ausschließlich das validierte Settings-Modell des aktuellen Moduls."""

    @overload
    def get(self, settings_type: type[TSettings]) -> TSettings | None: ...

    @overload
    def get(self, key: str, default: T | None = None) -> object | T | None: ...

    @overload
    def require(self, settings_type: type[TSettings]) -> TSettings: ...

    @overload
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
    permission_dependencies: PermissionDependencyFactory | None = None
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
    settings: ModuleSettingsContribution | None = None


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
    "JobDefinition",
    "JobHandler",
    "JobSchedule",
    "JsonScalar",
    "JsonValue",
    "LegacyJobHandler",
    "LifecycleRegistrar",
    "MetricsPort",
    "ModuleContext",
    "ModuleDefinition",
    "ModuleLifecycleHook",
    "ModuleManifestV1",
    "ModuleMigrationSource",
    "ModulePersistenceContribution",
    "ModulePrincipal",
    "ModulePrincipalDependency",
    "ModuleSettingsContribution",
    "ModuleSettingsPort",
    "ObservabilityPort",
    "PermissionDefinition",
    "PermissionDependencyFactory",
    "PermissionPort",
    "RetryPolicy",
    "SchedulerPort",
    "SerializableDomainEvent",
    "ServiceRegistryPort",
    "SpanPort",
    "StoragePort",
    "TracerPort",
    "event_envelope",
    "parse_manifest",
]
