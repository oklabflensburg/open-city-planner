"""Infrastrukturfreie Test-Fakes für Module, die das öffentliche SDK konsumieren."""

import json
import logging
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TypeVar, cast

from pydantic import BaseModel

from app.platform.modules.contracts import ModuleRegistrationContext
from app.platform.modules.sdk import (
    DomainEvent,
    EventEnvelope,
    EventHandler,
    HttpClientPort,
    HttpResponsePort,
    JobHandler,
    ModuleContext,
    ObservabilityPort,
    SerializableDomainEvent,
    SpanPort,
    event_envelope,
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
    def __init__(self) -> None:
        self.jobs: dict[str, JobHandler] = {}

    def register(self, job_id: str, handler: JobHandler) -> None:
        if job_id in self.jobs:
            raise ValueError(f'Test job "{job_id}" is already registered.')
        self.jobs[job_id] = handler


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
    return ModuleContext(
        module_id=module_id,
        module_version=module_version,
        api=registration,
        lifecycle=registration,
        observability=observability,
        events=FakeEventBus(),
        services=FakeServiceRegistry(),
        permissions=FakePermissions(),
        cache=FakeCache(module_id),
        storage=FakeStorage(module_id),
        http=FakeHttpClientFactory(),
        scheduler=FakeScheduler(),
        settings=FakeModuleSettings(settings, model=settings_model),
    )


__all__ = [
    "FakeCache",
    "FakeEventBus",
    "FakeHttpClient",
    "FakeHttpClientFactory",
    "FakeHttpResponse",
    "FakeMetrics",
    "FakeModuleSettings",
    "FakeObservability",
    "FakePermissions",
    "FakeScheduler",
    "FakeServiceRegistry",
    "FakeSpan",
    "FakeStorage",
    "FakeTracer",
    "create_test_module_context",
]
