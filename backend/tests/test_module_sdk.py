import ast
import subprocess
import sys
from dataclasses import FrozenInstanceError, dataclass
from pathlib import Path
from typing import Protocol, get_type_hints

import pytest
from fastapi import APIRouter, FastAPI

from app.platform.modules.context import ModuleContextFactory, ModuleHostServices
from app.platform.modules.contracts import ModuleRegistrationContext
from app.platform.modules.runtime import create_module_runtime
from app.platform.modules.sdk import (
    ApiRegistrar,
    CacheGenerationPort,
    CachePort,
    DatabaseSessionProvider,
    EventBusPort,
    HttpClientFactoryPort,
    LifecycleRegistrar,
    MapPreviewPort,
    ModuleContext,
    ModuleMigrationSource,
    ModuleSettingsPort,
    ObservabilityPort,
    PermissionDependencyFactory,
    PermissionPort,
    PolygonAnalyticsPort,
    PolygonQueryPort,
    PolygonScope,
    PublicQueryLimits,
    PublicQueryPort,
    SchedulerPort,
    ServiceRegistryPort,
    StatisticsQueryPort,
    StoragePort,
)
from app.platform.modules.testing import (
    FakeCache,
    FakeEventBus,
    FakeHttpClientFactory,
    FakeHttpResponse,
    FakeMetrics,
    FakeModuleSettings,
    FakeObservability,
    FakePermissions,
    FakeScheduler,
    FakeServiceRegistry,
    FakeStorage,
    FakeTracer,
    create_test_module_context,
)
from tests.fixtures.example_backend_module import DEFINITION as EXAMPLE_DEFINITION
from tests.test_module_runtime import FakeDiscovery, runtime_for


def test_module_context_has_typed_public_ports() -> None:
    hints = get_type_hints(ModuleContext)

    assert hints == {
        "module_id": str,
        "module_version": str,
        "api": ApiRegistrar,
        "lifecycle": LifecycleRegistrar,
        "observability": ObservabilityPort,
        "database": DatabaseSessionProvider | None,
        "events": EventBusPort | None,
        "services": ServiceRegistryPort | None,
        "permissions": PermissionPort | None,
        "permission_dependencies": PermissionDependencyFactory | None,
        "cache": CachePort | None,
        "cache_generations": CacheGenerationPort | None,
        "public_queries": PublicQueryPort | None,
        "map_previews": MapPreviewPort | None,
        "polygons": PolygonQueryPort | None,
        "polygon_analytics": PolygonAnalyticsPort | None,
        "statistics": StatisticsQueryPort | None,
        "storage": StoragePort | None,
        "http": HttpClientFactoryPort | None,
        "scheduler": SchedulerPort | None,
        "settings": ModuleSettingsPort | None,
    }


def test_migration_adoption_metadata_is_immutable_and_backward_compatible() -> None:
    default_source = ModuleMigrationSource(
        package="example_module",
        resource="migrations",
        revision_namespace="mod_example_module",
    )
    adopted_source = ModuleMigrationSource(
        package="example_module",
        resource="migrations",
        revision_namespace="mod_example_module",
        adopted_revisions=frozenset({"historical_001"}),
    )

    assert default_source.adopted_revisions == frozenset()
    assert adopted_source.adopted_revisions == frozenset({"historical_001"})
    with pytest.raises(FrozenInstanceError):
        adopted_source.adopted_revisions = frozenset()  # type: ignore[misc]


def test_migration_adoption_metadata_requires_exact_immutable_ids() -> None:
    with pytest.raises(TypeError, match="immutable frozenset"):
        ModuleMigrationSource(
            package="example_module",
            resource="migrations",
            revision_namespace="mod_example_module",
            adopted_revisions={"historical_001"},  # type: ignore[arg-type]
        )


def test_public_query_limits_are_validated_and_immutable() -> None:
    limits = PublicQueryLimits(max_response_items=100, cache_debug_headers=True)

    assert limits.max_response_items == 100
    with pytest.raises(FrozenInstanceError):
        limits.max_response_items = 10  # type: ignore[misc]
    with pytest.raises(ValueError, match="positive integers"):
        PublicQueryLimits(max_response_items=0)
    with pytest.raises(ValueError, match="non-empty exact IDs"):
        ModuleMigrationSource(
            package="example_module",
            resource="migrations",
            revision_namespace="mod_example_module",
            adopted_revisions=frozenset({" historical_001"}),
        )


def test_polygon_scope_is_primitive_immutable_and_validated() -> None:
    scope = PolygonScope((3, 5, 8))

    assert scope.polygon_ids == (3, 5, 8)
    with pytest.raises(FrozenInstanceError):
        scope.polygon_ids = (13,)  # type: ignore[misc]
    with pytest.raises(TypeError, match="immutable tuple"):
        PolygonScope([3, 5])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="positive integers"):
        PolygonScope((0,))
    with pytest.raises(ValueError, match="unique"):
        PolygonScope((3, 3))


def test_runtime_context_is_bound_to_manifest_and_unimplemented_ports_are_absent() -> None:
    runtime = runtime_for([EXAMPLE_DEFINITION])
    context = runtime.registry.get("test-example-module").context

    assert context.module_id == "test-example-module"
    assert context.module_version == "1.0.0"
    assert context.database is None
    assert context.events is None
    assert context.services is not None
    assert context.permissions is None
    assert context.permission_dependencies is None
    assert context.cache is None
    assert context.cache_generations is None
    assert context.public_queries is None
    assert context.map_previews is None
    assert context.polygons is None
    assert context.polygon_analytics is None
    assert context.statistics is None
    assert context.storage is None
    assert context.http is None
    assert context.scheduler is not None
    assert context.settings is None
    assert context.logger.extra == {
        "module_id": "test-example-module",
        "module_version": "1.0.0",
    }


def test_context_identity_is_immutable_and_registration_closes_with_runtime() -> None:
    runtime = runtime_for([EXAMPLE_DEFINITION])
    record = runtime.registry.get("test-example-module")

    with pytest.raises(FrozenInstanceError):
        record.context.module_id = "other-module"  # type: ignore[misc]

    runtime.register(FastAPI())
    with pytest.raises(RuntimeError, match="closed"):
        record.context.api.include_router(APIRouter())
    with pytest.raises(RuntimeError, match="closed"):
        record.context.lifecycle.add_lifecycle(startup=_noop_hook)


def test_public_context_registers_router_and_lifecycle_contributions() -> None:
    context = create_test_module_context()
    router = APIRouter()

    context.api.include_router(router, prefix="/example", tags=("Example",))
    context.lifecycle.add_lifecycle(startup=_noop_hook)

    registration = context.api
    assert isinstance(registration, ModuleRegistrationContext)
    assert registration.routers[0].prefix == "/example"
    assert registration.routers[0].tags == ("Example",)
    assert registration.lifecycle[0].startup is _noop_hook


async def _noop_hook() -> None:
    return None


def test_context_factory_supplies_explicit_host_adapter() -> None:
    cache = FakeCache("test-example-module")
    factory = ModuleContextFactory(ModuleHostServices(cache=cache))
    runtime = runtime_for_with_factory(factory)

    assert runtime.registry.get("test-example-module").context.cache is cache


def runtime_for_with_factory(factory: ModuleContextFactory):
    return create_module_runtime(
        enabled_module_ids=("test-example-module",),
        discovery_providers=(FakeDiscovery((EXAMPLE_DEFINITION,)),),
        host_version="0.2.0",
        context_factory=factory,
    )


@dataclass(frozen=True)
class ExampleEvent:
    event_type: str = "example.created"
    event_version: int = 1


class ExampleService(Protocol):
    def value(self) -> str: ...


class ExampleServiceImplementation:
    def value(self) -> str:
        return "ok"


@pytest.mark.asyncio
async def test_public_test_context_fakes_need_no_infrastructure() -> None:
    context = create_test_module_context(
        module_id="example-module",
        settings={"endpoint": "https://example.invalid"},
    )

    assert isinstance(context.cache, FakeCache)
    assert isinstance(context.events, FakeEventBus)
    assert isinstance(context.services, FakeServiceRegistry)
    assert isinstance(context.permissions, FakePermissions)
    assert isinstance(context.observability, FakeObservability)
    assert isinstance(context.storage, FakeStorage)
    assert isinstance(context.http, FakeHttpClientFactory)
    assert isinstance(context.scheduler, FakeScheduler)
    assert isinstance(context.settings, FakeModuleSettings)
    assert context.database is None

    assert await context.cache.set("key", b"value", ttl_seconds=30)
    assert await context.cache.get("key") == b"value"
    assert context.cache.ttls == {"key": 30}

    event = ExampleEvent()
    await context.events.publish(event)
    assert context.events.published == [event]

    service = ExampleServiceImplementation()
    context.services.services[ExampleService] = service
    assert context.services.resolve(ExampleService).value() == "ok"

    context.permissions.allowed.add("example-module.read")
    assert await context.permissions.is_allowed(
        "example-module.read", principal_id="user-1", resource_id="resource-1"
    )

    context.observability.metrics.increment("requests", attributes={"result": "ok"})
    with context.observability.tracer.span("load") as span:
        span.set_attribute("cached", True)
    assert context.observability.metrics.increments == [("requests", 1, {"result": "ok"})]
    assert context.observability.tracer.spans[0].attributes == {"cached": True}

    await context.storage.write("item", b"content", content_type="text/plain")
    assert await context.storage.read("item") == b"content"

    response = FakeHttpResponse(json_body={"status": "ok"})
    context.http.client.responses[("GET", "/status")] = response
    async with context.http.create(
        service_name="example", base_url="https://example.invalid"
    ) as client:
        assert (await client.request("GET", "/status")).json() == {"status": "ok"}

    context.scheduler.register("refresh", _noop_hook)
    assert tuple(context.scheduler.jobs) == ("example-module.refresh",)
    assert context.settings.require("endpoint") == "https://example.invalid"


def test_fake_metrics_and_tracer_are_concrete_test_ports() -> None:
    context = create_test_module_context()
    assert isinstance(context.observability.metrics, FakeMetrics)
    assert isinstance(context.observability.tracer, FakeTracer)


def test_public_sdk_import_does_not_start_application() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "from app.platform.modules.sdk import ModuleContext; "
                "assert ModuleContext; "
                "assert 'app.main' not in sys.modules"
            ),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_public_sdk_has_no_host_internal_or_domain_imports() -> None:
    sdk_path = Path(__file__).resolve().parents[1] / "app/platform/modules/sdk.py"
    tree = ast.parse(sdk_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    forbidden_prefixes = (
        "app.api",
        "app.cache",
        "app.core",
        "app.db",
        "app.models",
        "app.modules",
        "app.observability",
        "app.schemas",
        "app.security",
        "app.services",
    )
    assert not any(imported.startswith(forbidden_prefixes) for imported in imported_modules)

    forbidden_domain_names = {
        "AnalysisArea",
        "Assistant",
        "Notification",
        "OsmFeature",
        "Polygon",
        "SocialPublication",
        "Statistics",
    }
    assert forbidden_domain_names.isdisjoint(tree_names(tree))


@pytest.mark.parametrize(
    "fixture_name",
    ("example_backend_module.py", "example_persistence_module.py"),
)
def test_fixture_module_uses_only_public_app_sdk_import(fixture_name: str) -> None:
    fixture_path = Path(__file__).resolve().parent / f"fixtures/{fixture_name}"
    tree = ast.parse(fixture_path.read_text(encoding="utf-8"))
    app_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("app.")
    }
    assert app_imports == {"app.platform.modules.sdk"}


def tree_names(tree: ast.AST) -> set[str]:
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
