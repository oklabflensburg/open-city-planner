"""Infrastrukturfreie Test-Fakes für Module, die das öffentliche SDK konsumieren."""

import json
import logging
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import TypeVar, cast

from pydantic import BaseModel

from app.platform.modules.contracts import LifecycleContribution, ModuleRegistrationContext
from app.platform.modules.manifest import validate_manifest
from app.platform.modules.runtime import MODULE_SDK_VERSION
from app.platform.modules.sdk import (
    OSM_SNAPSHOT_QUERY_SERVICE_ID,
    OSM_SNAPSHOT_QUERY_SERVICE_VERSION,
    POLYGON_ASSIGNMENT_SERVICE_ID,
    POLYGON_ASSIGNMENT_SERVICE_VERSION,
    BackendModule,
    DomainEvent,
    EventEnvelope,
    EventHandler,
    HttpClientPort,
    HttpResponsePort,
    JobDefinition,
    LegacyJobHandler,
    ModuleContext,
    ModuleDefinition,
    ModuleManifestV1,
    ModulePrincipal,
    ObservabilityPort,
    OsmFeatureSnapshotPage,
    OsmSnapshotQuery,
    OsmSnapshotQueryPort,
    PolygonAssignmentPort,
    PolygonAssignmentRequest,
    PolygonAssignmentResult,
    SerializableDomainEvent,
    SpanPort,
    event_envelope,
    parse_manifest,
)

T = TypeVar("T")
TSettings = TypeVar("TSettings", bound=BaseModel)


class FakeCache:
    def __init__(self, module_id: str) -> None:
        self.module_id = module_id
        self.values: dict[str, bytes] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str) -> bytes | None:
        return self.values.get(key)

    async def set(self, key: str, value: bytes, *, ttl_seconds: int) -> bool:
        if ttl_seconds <= 0:
            raise ValueError("Cache TTL must be a positive number of seconds.")
        self.values[key] = value
        self.ttls[key] = ttl_seconds
        return True

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self.values:
                deleted += 1
                self.values.pop(key)
                self.ttls.pop(key, None)
        return deleted

    async def clear(self) -> int:
        deleted = len(self.values)
        self.values.clear()
        self.ttls.clear()
        return deleted


class FakeCacheGenerations:
    """In-memory cache-generation port for isolated module contract tests."""

    def __init__(self, generations: Mapping[str, int] | None = None) -> None:
        self.generations = dict(generations or {})
        self.bump_calls: list[tuple[str, ...]] = []

    async def current(self, session, resource: str) -> int:
        del session
        return self.generations.get(resource, 1)

    async def bump(self, session, resources: Sequence[str]) -> None:
        del session
        unique_resources = tuple(dict.fromkeys(resources))
        self.bump_calls.append(unique_resources)
        for resource in unique_resources:
            self.generations[resource] = self.generations.get(resource, 1) + 1


class FakeEventBus:
    def __init__(self) -> None:
        self.published: list[DomainEvent | SerializableDomainEvent | EventEnvelope] = []
        self.queued: list[EventEnvelope] = []
        self.subscriptions: list[tuple[str, str, frozenset[int], EventHandler]] = []

    async def publish(
        self, event: DomainEvent | SerializableDomainEvent | EventEnvelope
    ) -> None:
        self.published.append(event)

    async def publish_after_commit(
        self,
        event: DomainEvent | SerializableDomainEvent | EventEnvelope,
        *,
        session,
    ) -> EventEnvelope:
        del session
        envelope = event if isinstance(event, EventEnvelope) else event_envelope(event)
        self.queued.append(envelope)
        return envelope

    def subscribe(
        self,
        event_name: str,
        *,
        handler_id: str,
        versions: frozenset[int],
        handler: EventHandler,
    ) -> None:
        self.subscriptions.append((event_name, handler_id, versions, handler))


class FakeServiceRegistry:
    def __init__(self, services: Mapping[type[object], object] | None = None) -> None:
        self.services = dict(services or {})
        self.versioned_services: dict[tuple[str, int], tuple[type[object], object]] = {}
        self.sealed = False

    def register(
        self,
        contract: type[T],
        implementation: T,
        *,
        service_id: str,
        version: int,
        deprecated_since: str | None = None,
        replacement: str | None = None,
    ) -> None:
        del deprecated_since, replacement
        if self.sealed:
            raise RuntimeError("The fake service registry is sealed.")
        key = (service_id, version)
        if key in self.versioned_services:
            raise ValueError(f'Test service "{service_id}" version {version} is duplicated.')
        self.versioned_services[key] = (cast(type[object], contract), implementation)
        self.services[contract] = implementation

    def require(self, contract: type[T], *, service_id: str, version: int) -> T:
        key = (service_id, version)
        if key not in self.versioned_services:
            raise LookupError(f'No test service "{service_id}" version {version} is registered.')
        registered_contract, implementation = self.versioned_services[key]
        if registered_contract is not contract:
            raise TypeError(f'Test service "{service_id}" uses a different contract.')
        return cast(T, implementation)

    def optional(self, contract: type[T], *, service_id: str, version: int) -> T | None:
        key = (service_id, version)
        if key not in self.versioned_services:
            return None
        return self.require(contract, service_id=service_id, version=version)

    def resolve(self, contract: type[T]) -> T:
        if contract not in self.services:
            raise LookupError(f"No test service is registered for {contract.__name__}.")
        return cast(T, self.services[contract])

    def seal(self) -> None:
        self.sealed = True


class FakeOsmSnapshotQueries:
    """Scriptable public OSM snapshot fake for external module tests."""

    def __init__(self, pages: Sequence[OsmFeatureSnapshotPage] = ()) -> None:
        self.pages = list(pages)
        self.calls: list[OsmSnapshotQuery] = []

    async def list_features(self, session, query: OsmSnapshotQuery) -> OsmFeatureSnapshotPage:
        del session
        self.calls.append(query)
        if self.pages:
            return self.pages.pop(0)
        return OsmFeatureSnapshotPage(items=())


class FakePolygonAssignments:
    """Deterministic assignment fake recording immutable requests."""

    def __init__(self, result: PolygonAssignmentResult | None = None) -> None:
        self.result = result or PolygonAssignmentResult(0, 0, 0, 0, 0)
        self.calls: list[PolygonAssignmentRequest] = []

    async def refresh_assignments(
        self, session, request: PolygonAssignmentRequest
    ) -> PolygonAssignmentResult:
        del session
        self.calls.append(request)
        return self.result


class FakePermissions:
    def __init__(self, allowed: set[str] | None = None) -> None:
        self.allowed = set(allowed or ())
        self.checks: list[tuple[str, str | None, str | None]] = []

    async def is_allowed(
        self,
        permission_id: str,
        *,
        principal_id: str | None,
        resource_id: str | None = None,
    ) -> bool:
        self.checks.append((permission_id, principal_id, resource_id))
        return permission_id in self.allowed


class FakePermissionDependencies:
    def __init__(self, principal_id: str = "test-user") -> None:
        self.principal_id = principal_id
        self.requirements: list[tuple[str, bool]] = []

    def require(self, permission_id: str, *, csrf: bool = False):
        self.requirements.append((permission_id, csrf))

        async def dependency() -> ModulePrincipal:
            return ModulePrincipal(id=self.principal_id)

        return dependency


class FakeMetrics:
    def __init__(self) -> None:
        self.increments: list[tuple[str, float, Mapping[str, str]]] = []
        self.observations: list[tuple[str, float, Mapping[str, str]]] = []

    def increment(
        self,
        name: str,
        *,
        value: float = 1,
        attributes: Mapping[str, str] | None = None,
    ) -> None:
        self.increments.append((name, value, dict(attributes or {})))

    def observe(
        self,
        name: str,
        value: float,
        *,
        attributes: Mapping[str, str] | None = None,
    ) -> None:
        self.observations.append((name, value, dict(attributes or {})))


@dataclass(slots=True)
class FakeSpan:
    name: str
    attributes: dict[str, str | float | bool] = field(default_factory=dict)
    exceptions: list[Exception] = field(default_factory=list)

    def set_attribute(self, name: str, value: str | float | bool) -> None:
        self.attributes[name] = value

    def record_exception(self, error: Exception) -> None:
        self.exceptions.append(error)


class FakeTracer:
    def __init__(self) -> None:
        self.spans: list[FakeSpan] = []

    @contextmanager
    def span(
        self,
        name: str,
        *,
        attributes: Mapping[str, str] | None = None,
    ):
        span = FakeSpan(name, dict(attributes or {}))
        self.spans.append(span)
        yield cast(SpanPort, span)


@dataclass(frozen=True, slots=True)
class FakeObservability:
    logger: logging.LoggerAdapter
    metrics: FakeMetrics
    tracer: FakeTracer


class FakeStorage:
    def __init__(self, module_id: str) -> None:
        self.module_id = module_id
        self.values: dict[str, bytes] = {}
        self.content_types: dict[str, str | None] = {}

    async def read(self, key: str) -> bytes | None:
        return self.values.get(key)

    async def write(self, key: str, value: bytes, *, content_type: str | None = None) -> None:
        self.values[key] = value
        self.content_types[key] = content_type

    async def delete(self, key: str) -> bool:
        existed = key in self.values
        self.values.pop(key, None)
        self.content_types.pop(key, None)
        return existed

    async def exists(self, key: str) -> bool:
        return key in self.values


@dataclass(frozen=True, slots=True)
class FakeHttpResponse:
    status_code: int = 200
    headers: Mapping[str, str] = field(default_factory=dict)
    content: bytes = b""
    json_body: object | None = None

    def json(self) -> object:
        if self.json_body is not None:
            return self.json_body
        return json.loads(self.content)


class FakeHttpClient:
    def __init__(self) -> None:
        self.responses: dict[tuple[str, str], HttpResponsePort] = {}
        self.requests: list[tuple[str, str]] = []

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        content: bytes | None = None,
    ) -> HttpResponsePort:
        del headers, params, content
        key = (method.upper(), url)
        self.requests.append(key)
        if key not in self.responses:
            raise LookupError(f"No fake HTTP response is configured for {key[0]} {key[1]}.")
        return self.responses[key]


class FakeHttpClientFactory:
    def __init__(self, client: FakeHttpClient | None = None) -> None:
        self.client = client or FakeHttpClient()
        self.created: list[tuple[str, str | None]] = []

    @asynccontextmanager
    async def create(
        self,
        *,
        service_name: str,
        base_url: str | None = None,
    ) -> AsyncIterator[HttpClientPort]:
        self.created.append((service_name, base_url))
        yield self.client


class FakeScheduler:
    def __init__(self, module_id: str | None = None) -> None:
        self.module_id = module_id
        self.jobs: dict[str, JobDefinition] = {}

    def register(
        self,
        definition: JobDefinition | str,
        handler: LegacyJobHandler | None = None,
    ) -> None:
        if isinstance(definition, str):
            if handler is None:
                raise TypeError("Compatibility job registration requires a handler.")

            async def invoke(_context: ModuleContext) -> object | None:
                return await handler()

            definition = JobDefinition(job_id=definition, handler=invoke)
        elif handler is not None:
            raise TypeError("JobDefinition registration does not accept a second handler.")
        if "." not in definition.job_id and self.module_id is not None:
            definition = replace(
                definition,
                job_id=f"{self.module_id}.{definition.job_id}",
            )
        if definition.job_id in self.jobs:
            raise ValueError(f'Test job "{definition.job_id}" is already registered.')
        self.jobs[definition.job_id] = definition

    async def run(self, job_id: str, context: ModuleContext) -> object | None:
        return await self.jobs[job_id].handler(context)


class FakeJobRegistry(FakeScheduler):
    """Benannter Job-Registry-Fake für Modultests ohne Host-Runner."""


class FakeModuleSettings:
    def __init__(
        self,
        values: Mapping[str, object] | None = None,
        *,
        model: BaseModel | None = None,
    ) -> None:
        self.values = MappingProxyType(dict(values or {}))
        self.model = model

    def get(
        self,
        settings_type_or_key: type[TSettings] | str,
        default: T | None = None,
    ) -> TSettings | object | T | None:
        if isinstance(settings_type_or_key, str):
            return self.values.get(settings_type_or_key, default)
        if self.model is not None and isinstance(self.model, settings_type_or_key):
            return cast(TSettings, self.model)
        return None

    def require(self, settings_type_or_key: type[TSettings] | str) -> TSettings | object:
        value = self.get(settings_type_or_key)
        if value is None:
            raise KeyError(
                settings_type_or_key
                if isinstance(settings_type_or_key, str)
                else settings_type_or_key.__name__
            )
        return value


class ModuleTestHost:
    """Kleiner Modul-Lifecycle fuer Contract-Tests ohne produktive Infrastruktur."""

    def __init__(
        self,
        definition: ModuleDefinition,
        *,
        host_version: str = "0.2.0",
        sdk_version: str = MODULE_SDK_VERSION,
        settings: Mapping[str, object] | None = None,
    ) -> None:
        manifest = (
            definition.manifest
            if isinstance(definition.manifest, ModuleManifestV1)
            else parse_manifest(definition.manifest, origin=definition.origin)
        )
        if definition.declared_id != manifest.id:
            raise ValueError("The test module discovery ID does not match its manifest ID.")
        self.manifest = validate_manifest(
            manifest,
            host_version=host_version,
            sdk_version=sdk_version,
        )
        self.definition = definition
        self.module: BackendModule = definition.loader()
        if self.module.manifest.id != self.manifest.id:
            raise ValueError("The loaded test module does not match its definition manifest.")
        self.context = create_test_module_context(
            module_id=self.manifest.id,
            module_version=self.manifest.version,
            settings=settings,
        )
        self._registered = False
        self._started: list[LifecycleContribution] = []

    def register(self) -> ModuleContext:
        if self._registered:
            raise RuntimeError("The test module is already registered.")
        registration = cast(ModuleRegistrationContext, self.context.api)
        try:
            self.module.register(self.context)
        finally:
            registration.close()
            services = self.context.services
            if isinstance(services, FakeServiceRegistry):
                services.seal()
            self._registered = True
        return self.context

    async def startup(self) -> None:
        if not self._registered:
            self.register()
        registration = cast(ModuleRegistrationContext, self.context.lifecycle)
        for contribution in registration.lifecycle:
            if contribution.startup is not None:
                await contribution.startup()
                self._started.append(contribution)

    async def shutdown(self) -> None:
        for contribution in reversed(self._started):
            if contribution.shutdown is not None:
                await contribution.shutdown()
        self._started.clear()


def create_test_module_context(
    *,
    module_id: str = "test-module",
    module_version: str = "1.0.0",
    settings: Mapping[str, object] | None = None,
    settings_model: BaseModel | None = None,
) -> ModuleContext:
    """Erzeuge einen vollständigen Context ohne DB, Redis, Netzwerk oder Dateisystem."""

    registration = ModuleRegistrationContext()
    observability: ObservabilityPort = FakeObservability(
        logger=logging.LoggerAdapter(
            logging.getLogger(f"tests.modules.{module_id}"),
            {"module_id": module_id, "module_version": module_version},
        ),
        metrics=FakeMetrics(),
        tracer=FakeTracer(),
    )
    service_registry = FakeServiceRegistry()
    service_registry.register(
        OsmSnapshotQueryPort,
        FakeOsmSnapshotQueries(),
        service_id=OSM_SNAPSHOT_QUERY_SERVICE_ID,
        version=OSM_SNAPSHOT_QUERY_SERVICE_VERSION,
    )
    service_registry.register(
        PolygonAssignmentPort,
        FakePolygonAssignments(),
        service_id=POLYGON_ASSIGNMENT_SERVICE_ID,
        version=POLYGON_ASSIGNMENT_SERVICE_VERSION,
    )
    return ModuleContext(
        module_id=module_id,
        module_version=module_version,
        api=registration,
        lifecycle=registration,
        observability=observability,
        events=FakeEventBus(),
        services=service_registry,
        permissions=FakePermissions(),
        permission_dependencies=FakePermissionDependencies(),
        cache=FakeCache(module_id),
        cache_generations=FakeCacheGenerations(),
        storage=FakeStorage(module_id),
        http=FakeHttpClientFactory(),
        scheduler=FakeJobRegistry(module_id),
        settings=FakeModuleSettings(settings, model=settings_model),
    )


__all__ = [
    "FakeCache",
    "FakeCacheGenerations",
    "FakeEventBus",
    "FakeHttpClient",
    "FakeHttpClientFactory",
    "FakeHttpResponse",
    "FakeJobRegistry",
    "FakeMetrics",
    "FakeModuleSettings",
    "FakeObservability",
    "FakeOsmSnapshotQueries",
    "FakePermissionDependencies",
    "FakePermissions",
    "FakePolygonAssignments",
    "FakeScheduler",
    "FakeServiceRegistry",
    "FakeSpan",
    "FakeStorage",
    "FakeTracer",
    "ModuleTestHost",
    "create_test_module_context",
]
