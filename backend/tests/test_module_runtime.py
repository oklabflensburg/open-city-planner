from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from app.api.router import api_router
from app.platform.events import InProcessEventBus
from app.platform.modules import (
    DuplicateModuleIdError,
    EntryPointModuleDiscovery,
    FirstPartyModuleDiscovery,
    MissingModuleDependencyError,
    ModuleCompatibilityError,
    ModuleContext,
    ModuleDefinition,
    ModuleDependencyCycleError,
    ModuleDiscoveryError,
    ModuleLoadError,
    ModuleManifestV1,
    ModuleRegistrationContext,
    ModuleRegistrationError,
    ModuleShutdownError,
    ModuleStartupError,
    ModuleValidationError,
    create_module_runtime,
    parse_manifest,
)
from app.platform.modules import discovery as discovery_module
from app.platform.modules.context import ModuleContextFactory
from app.platform.modules.contracts import ModuleDiscoveryProvider
from app.platform.modules.discovery import ENTRY_POINT_GROUP
from tests.fixtures.example_backend_module import DEFINITION as EXAMPLE_DEFINITION


def manifest_data(
    module_id: str,
    *,
    required: dict[str, str] | None = None,
    optional: dict[str, str] | None = None,
    host: str = ">=0.2.0,<1.0.0",
    sdk: str = ">=1.0.0,<2.0.0",
    capabilities: list[str] | None = None,
    permissions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "manifest_version": 1,
        "id": module_id,
        "name": module_id,
        "version": "1.0.0",
        "requires": {"host": host, "sdk": sdk, "modules": required or {}},
        "optional": {"modules": optional or {}},
        "capabilities": capabilities or [],
        "permissions": permissions or [],
    }


class RecordingModule:
    def __init__(
        self,
        manifest: ModuleManifestV1,
        *,
        events: list[str] | None = None,
        registration_error: Exception | None = None,
        startup_error: Exception | None = None,
    ) -> None:
        self.manifest = manifest
        self.events = events
        self.registration_error = registration_error
        self.startup_error = startup_error

    def register(self, context: ModuleRegistrationContext) -> None:
        if self.registration_error is not None:
            raise self.registration_error
        if self.events is None:
            return

        async def startup() -> None:
            self.events.append(f"start:{self.manifest.id}")
            if self.startup_error is not None:
                raise self.startup_error

        async def shutdown() -> None:
            self.events.append(f"stop:{self.manifest.id}")

        context.add_lifecycle(startup=startup, shutdown=shutdown)


def definition(
    module_id: str,
    *,
    required: dict[str, str] | None = None,
    optional: dict[str, str] | None = None,
    host: str = ">=0.2.0,<1.0.0",
    sdk: str = ">=1.0.0,<2.0.0",
    events: list[str] | None = None,
    registration_error: Exception | None = None,
    startup_error: Exception | None = None,
    capabilities: list[str] | None = None,
    permissions: list[str] | None = None,
) -> ModuleDefinition:
    manifest = parse_manifest(
        manifest_data(
            module_id,
            required=required,
            optional=optional,
            host=host,
            sdk=sdk,
            capabilities=capabilities,
            permissions=permissions,
        )
    )
    return ModuleDefinition(
        manifest=manifest,
        loader=lambda: RecordingModule(
            manifest,
            events=events,
            registration_error=registration_error,
            startup_error=startup_error,
        ),
        origin=f"test:{module_id}",
        declared_id=module_id,
    )


@dataclass
class FakeDiscovery(ModuleDiscoveryProvider):
    definitions: Sequence[ModuleDefinition]

    def discover(self, enabled_module_ids: frozenset[str]) -> Sequence[ModuleDefinition]:
        return self.definitions


def runtime_for(
    definitions: Sequence[ModuleDefinition],
    *,
    enabled: Sequence[str] | None = None,
    host_version: str = "0.2.0",
    sdk_version: str = "1.0.0",
):
    enabled_module_ids = (
        [definition.declared_id for definition in definitions] if enabled is None else enabled
    )
    return create_module_runtime(
        enabled_module_ids=enabled_module_ids,
        discovery_providers=(FakeDiscovery(definitions),),
        host_version=host_version,
        sdk_version=sdk_version,
    )


def test_no_enabled_module_creates_empty_runtime() -> None:
    runtime = runtime_for([], enabled=[])
    assert runtime.module_ids == ()


def test_first_party_discovery_loads_only_enabled_definitions() -> None:
    loaded: list[str] = []

    def source(module_id: str) -> Callable[[], ModuleDefinition]:
        def load() -> ModuleDefinition:
            loaded.append(module_id)
            return definition(module_id)

        return load

    provider = FirstPartyModuleDiscovery(
        {"module-a": source("module-a"), "module-b": source("module-b")}
    )
    runtime = create_module_runtime(
        enabled_module_ids=("module-b",),
        discovery_providers=(provider,),
        host_version="0.2.0",
    )

    assert runtime.module_ids == ("module-b",)
    assert loaded == ["module-b"]


def test_first_party_available_discovery_is_generic_and_does_not_enable_runtime() -> None:
    provider = FirstPartyModuleDiscovery()

    available = provider.discover_available()
    runtime = create_module_runtime(
        enabled_module_ids=(),
        discovery_providers=(provider,),
        host_version="0.2.0",
    )

    assert {definition.declared_id for definition in available} >= {
        "analysis-areas",
        "reference",
    }
    assert runtime.module_ids == ()


def test_runtime_ignores_disabled_definition_returned_by_provider() -> None:
    disabled = ModuleDefinition(
        manifest={"manifest_version": 1, "id": "INVALID"},
        loader=lambda: None,  # type: ignore[arg-type,return-value]
        origin="test:disabled",
        declared_id="disabled-module",
    )
    runtime = runtime_for([disabled], enabled=[])
    assert runtime.module_ids == ()


def test_multiple_modules_use_lexicographic_tie_breaking() -> None:
    runtime = runtime_for([definition("module-z"), definition("module-a")])
    assert runtime.module_ids == ("module-a", "module-z")


def test_duplicate_module_id_preserves_manifest_error_as_cause() -> None:
    duplicate = definition("duplicate-module")
    with pytest.raises(ModuleValidationError) as error:
        runtime_for([duplicate, duplicate])

    assert error.value.phase == "validation"
    assert error.value.module_id == "duplicate-module"
    assert isinstance(error.value.__cause__, DuplicateModuleIdError)


def test_invalid_manifest_is_reported_in_validation_phase() -> None:
    invalid = ModuleDefinition(
        manifest={"manifest_version": 1, "id": "INVALID"},
        loader=lambda: None,  # type: ignore[arg-type,return-value]
        origin="test:invalid",
        declared_id="invalid",
    )
    with pytest.raises(ModuleValidationError) as error:
        runtime_for([invalid], enabled=("invalid",))

    assert error.value.phase == "validation"
    assert error.value.origin == "test:invalid"


@pytest.mark.parametrize(
    ("target", "definition_value", "host_version", "sdk_version"),
    [
        ("host", definition("host-incompatible", host=">=2.0.0,<3.0.0"), "0.2.0", "1.0.0"),
        ("sdk", definition("sdk-incompatible", sdk=">=2.0.0,<3.0.0"), "0.2.0", "1.0.0"),
    ],
)
def test_incompatible_runtime_version_is_fail_fast(
    target: str,
    definition_value: ModuleDefinition,
    host_version: str,
    sdk_version: str,
) -> None:
    with pytest.raises(ModuleValidationError) as error:
        runtime_for([definition_value], host_version=host_version, sdk_version=sdk_version)

    assert isinstance(error.value.__cause__, ModuleCompatibilityError)
    assert error.value.__cause__.target == target
    assert error.value.module_id == definition_value.declared_id
    assert error.value.origin == f"test:{definition_value.declared_id}"


def test_required_dependency_and_optional_dependency_define_load_order() -> None:
    runtime = runtime_for(
        [
            definition(
                "consumer",
                required={"required-base": ">=1.0.0,<2.0.0"},
                optional={"optional-base": ">=1.0.0,<2.0.0"},
            ),
            definition("required-base"),
            definition("optional-base"),
        ]
    )
    assert runtime.module_ids == ("optional-base", "required-base", "consumer")


def test_required_dependency_on_disabled_module_fails() -> None:
    consumer = definition("consumer", required={"disabled-base": ">=1.0.0,<2.0.0"})
    with pytest.raises(ModuleValidationError) as error:
        runtime_for([consumer], enabled=("consumer",))

    assert isinstance(error.value.__cause__, MissingModuleDependencyError)


def test_optional_dependency_on_disabled_module_still_allows_registration() -> None:
    consumer = definition(
        "consumer", optional={"disabled-base": ">=1.0.0,<2.0.0"}
    )
    runtime = runtime_for([consumer], enabled=("consumer",))

    runtime.register(FastAPI())

    assert runtime.module_ids == ("consumer",)
    assert runtime.operational_status.modules[0].registered is True


def test_dependency_cycle_is_reported_by_manifest_graph() -> None:
    module_a = definition("module-a", required={"module-b": ">=1.0.0,<2.0.0"})
    module_b = definition("module-b", required={"module-a": ">=1.0.0,<2.0.0"})
    with pytest.raises(ModuleValidationError) as error:
        runtime_for([module_a, module_b])

    assert isinstance(error.value.__cause__, ModuleDependencyCycleError)


def test_enabled_unknown_module_fails_discovery() -> None:
    with pytest.raises(ModuleDiscoveryError, match="module_id=missing-module"):
        runtime_for([], enabled=("missing-module",))


def test_loader_failure_contains_import_phase_and_module_id() -> None:
    manifest = parse_manifest(manifest_data("broken-module"))

    def broken_loader():
        raise ImportError("broken import")

    broken = ModuleDefinition(manifest, broken_loader, "test:broken", "broken-module")
    with pytest.raises(ModuleLoadError) as error:
        runtime_for([broken])

    assert error.value.phase == "import"
    assert error.value.module_id == "broken-module"
    assert isinstance(error.value.__cause__, ImportError)

def test_registry_exposes_manifest_capabilities() -> None:
    runtime = runtime_for([definition("capable-module", capabilities=["map.layer"])])
    assert runtime.registry.capabilities("capable-module") == ("map.layer",)


def test_runtime_exposes_only_enabled_module_permissions_and_seals_them() -> None:
    runtime = runtime_for(
        [
            definition("enabled-module", permissions=["enabled-module.use"]),
            definition("disabled-module", permissions=["disabled-module.use"]),
        ],
        enabled=("enabled-module",),
    )
    runtime.register(FastAPI())

    assert runtime.permission_registry.permission_ids == ("enabled-module.use",)
    assert runtime.permission_registry.sealed is True


def test_registration_failure_is_fail_fast_and_registration_is_single_use() -> None:
    broken = runtime_for(
        [definition("broken-module", registration_error=RuntimeError("register failed"))]
    )
    with pytest.raises(ModuleRegistrationError, match="module_id=broken-module"):
        broken.register(FastAPI())
    assert broken.operational_status.modules[0].status == "loaded"
    assert broken.operational_status.modules[0].registered is False

    runtime = runtime_for([])
    app = FastAPI()
    runtime.register(app)
    with pytest.raises(ModuleRegistrationError, match="already attached"):
        runtime.register(app)


@pytest.mark.asyncio
async def test_partial_registration_failure_does_not_attach_collected_routers() -> None:
    runtime = runtime_for(
        [
            EXAMPLE_DEFINITION,
            definition(
                "z-broken-module",
                registration_error=RuntimeError("register failed"),
            ),
        ]
    )
    app = FastAPI()

    with pytest.raises(ModuleRegistrationError) as error:
        runtime.register(app)

    assert error.value.module_id == "z-broken-module"
    assert error.value.origin == "test:z-broken-module"
    assert [module.registered for module in runtime.operational_status.modules] == [
        True,
        False,
    ]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/module-test/ping")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_router_registration_coexists_with_legacy_router() -> None:
    runtime = runtime_for([EXAMPLE_DEFINITION])
    app = FastAPI()
    app.include_router(api_router)
    runtime.register(app)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        module_response = await client.get("/api/v1/module-test/ping")
        legacy_response = await client.get("/api/v1/auth/providers")

    assert module_response.status_code == 200
    assert module_response.json() == {"status": "ok"}
    assert legacy_response.status_code == 200
    assert "providers" in legacy_response.json()


@pytest.mark.asyncio
async def test_disabled_fixture_module_has_no_route() -> None:
    runtime = runtime_for([], enabled=[])
    app = FastAPI()
    runtime.register(app)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/module-test/ping")
    assert response.status_code == 404


def test_disabled_module_registers_no_event_subscriber_or_lifecycle_hook() -> None:
    manifest = parse_manifest(manifest_data("subscriber-module"))
    event_bus = InProcessEventBus()
    loaded: list[str] = []

    class SubscriberModule:
        def __init__(self) -> None:
            self.manifest = manifest
            loaded.append("loaded")

        def register(self, context: ModuleContext) -> None:
            assert context.events is not None

            async def handle(_event) -> None:
                return None

            context.events.subscribe(
                "publisher.changed",
                handler_id="subscriber-module.handle-change",
                versions=frozenset({1}),
                handler=handle,
            )

            async def startup() -> None:
                return None

            context.lifecycle.add_lifecycle(startup=startup)

    disabled = ModuleDefinition(
        manifest,
        SubscriberModule,
        "test:subscriber-module",
        "subscriber-module",
    )
    runtime = create_module_runtime(
        enabled_module_ids=(),
        discovery_providers=(FakeDiscovery((disabled,)),),
        host_version="0.2.0",
        context_factory=ModuleContextFactory(event_bus=event_bus),
    )
    runtime.register(FastAPI())

    assert runtime.module_ids == ()
    assert loaded == []
    assert event_bus.subscriptions == ()


@pytest.mark.asyncio
async def test_lifecycle_uses_load_order_and_reverse_shutdown_order() -> None:
    events: list[str] = []
    runtime = runtime_for(
        [
            definition("consumer", required={"base-module": ">=1.0.0,<2.0.0"}, events=events),
            definition("base-module", events=events),
        ]
    )
    runtime.register(FastAPI())
    await runtime.startup()
    await runtime.shutdown()

    assert events == [
        "start:base-module",
        "start:consumer",
        "stop:consumer",
        "stop:base-module",
    ]


@pytest.mark.asyncio
async def test_startup_failure_cleans_up_already_started_modules() -> None:
    events: list[str] = []
    runtime = runtime_for(
        [
            definition("module-a", events=events),
            definition("module-b", events=events, startup_error=RuntimeError("startup failed")),
        ]
    )
    runtime.register(FastAPI())

    with pytest.raises(ModuleStartupError) as error:
        await runtime.startup()

    assert error.value.module_id == "module-b"
    assert events == ["start:module-a", "start:module-b", "stop:module-a"]
    assert {module.status for module in runtime.operational_status.modules} == {"registered"}
    await runtime.shutdown()


@pytest.mark.asyncio
async def test_shutdown_failure_does_not_skip_earlier_modules() -> None:
    events: list[str] = []
    module_a = definition("module-a", events=events)
    manifest_b = parse_manifest(manifest_data("module-b"))

    class FailingShutdownModule(RecordingModule):
        def register(self, context: ModuleRegistrationContext) -> None:
            async def startup() -> None:
                events.append("start:module-b")

            async def shutdown() -> None:
                events.append("stop:module-b")
                raise RuntimeError("shutdown failed")

            context.add_lifecycle(startup=startup, shutdown=shutdown)

    module_b = ModuleDefinition(
        manifest=manifest_b,
        loader=lambda: FailingShutdownModule(manifest_b),
        origin="test:module-b",
        declared_id="module-b",
    )
    runtime = runtime_for([module_a, module_b])
    runtime.register(FastAPI())
    await runtime.startup()

    with pytest.raises(ModuleShutdownError) as error:
        await runtime.shutdown()

    assert error.value.module_id == "module-b"
    assert events == ["start:module-a", "start:module-b", "stop:module-b", "stop:module-a"]


class FakeEntryPoints(list):
    def select(self, *, group: str):
        assert group == ENTRY_POINT_GROUP
        return self


class FakeEntryPoint:
    def __init__(self, name: str, value: str, result: object) -> None:
        self.name = name
        self.value = value
        self.result = result
        self.load_count = 0

    def load(self) -> object:
        self.load_count += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_entry_point_discovery_loads_only_enabled_group_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enabled = FakeEntryPoint("test-example-module", "package:definition", EXAMPLE_DEFINITION)
    disabled = FakeEntryPoint("disabled-module", "other:definition", RuntimeError("must not load"))
    monkeypatch.setattr(
        discovery_module.metadata, "entry_points", lambda: FakeEntryPoints([disabled, enabled])
    )

    runtime = create_module_runtime(
        enabled_module_ids=("test-example-module",),
        discovery_providers=(EntryPointModuleDiscovery(),),
        host_version="0.2.0",
    )

    assert runtime.module_ids == ("test-example-module",)
    assert enabled.load_count == 1
    assert disabled.load_count == 0


def test_entry_point_available_discovery_loads_passive_installed_definitions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installed = FakeEntryPoint(
        "test-example-module", "package:definition", EXAMPLE_DEFINITION
    )
    monkeypatch.setattr(
        discovery_module.metadata, "entry_points", lambda: FakeEntryPoints([installed])
    )

    available = EntryPointModuleDiscovery().discover_available()

    assert [definition.declared_id for definition in available] == [
        "test-example-module"
    ]
    assert available[0].origin == (
        "entry-point:test-example-module=package:definition"
    )
    assert installed.load_count == 1


def test_broken_enabled_entry_point_has_discovery_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = FakeEntryPoint("broken-module", "broken:definition", ImportError("broken"))
    monkeypatch.setattr(
        discovery_module.metadata, "entry_points", lambda: FakeEntryPoints([broken])
    )

    with pytest.raises(ModuleDiscoveryError) as error:
        create_module_runtime(
            enabled_module_ids=("broken-module",),
            discovery_providers=(EntryPointModuleDiscovery(),),
            host_version="0.2.0",
        )

    assert error.value.module_id == "broken-module"
    assert error.value.phase == "discovery"
    assert isinstance(error.value.__cause__, ImportError)
