from dataclasses import is_dataclass
from typing import Protocol

import pytest
from fastapi import FastAPI

from app.platform.modules.context import ModuleContextFactory
from app.platform.modules.errors import (
    DuplicateServiceRegistrationError,
    IncompatibleServiceVersionError,
    MissingRequiredServiceError,
    ModuleRegistrationError,
    ServiceContractMismatchError,
    ServiceRegistryError,
    ServiceRegistrySealedError,
    UndeclaredServiceDependencyError,
)
from app.platform.modules.manifest import parse_manifest
from app.platform.modules.runtime import create_module_runtime
from app.platform.modules.sdk import ModuleContext, ModuleDefinition
from app.platform.modules.services import ServiceRegistry
from app.platform.modules.testing import FakeServiceRegistry
from tests.fixtures.service_modules.analysis_areas.contracts import (
    SERVICE_ID,
    AnalysisAreaQueryService,
    AnalysisAreaSummary,
)
from tests.fixtures.service_modules.analysis_areas.module import DEFINITION as PROVIDER
from tests.fixtures.service_modules.statistics.module import DEFINITION as CONSUMER
from tests.fixtures.service_modules.statistics.module import StatisticsFixtureModule
from tests.test_module_runtime import FakeDiscovery


class ExampleContract(Protocol):
    def value(self) -> str: ...


class OtherContract(Protocol):
    def other(self) -> str: ...


class ExampleImplementation:
    def __init__(self, value: str = "ok") -> None:
        self._value = value

    def value(self) -> str:
        return self._value


def manifest(
    module_id: str,
    *,
    required: dict[str, str] | None = None,
    optional: dict[str, str] | None = None,
):
    return parse_manifest(
        {
            "manifest_version": 1,
            "id": module_id,
            "name": module_id,
            "version": "1.0.0",
            "requires": {
                "host": ">=0.2.0,<1.0.0",
                "sdk": ">=1.3.0,<2.0.0",
                "modules": required or {},
            },
            "optional": {"modules": optional or {}},
        }
    )


def bound_registries():
    registry = ServiceRegistry()
    provider = registry.bind(manifest("provider-module"))
    consumer = registry.bind(
        manifest("consumer-module", required={"provider-module": ">=1.0.0,<2.0.0"})
    )
    return registry, provider, consumer


def test_register_and_typed_required_lookup() -> None:
    _, provider, consumer = bound_registries()
    implementation = ExampleImplementation()

    provider.register(
        ExampleContract,
        implementation,
        service_id="provider-module.example",
        version=1,
    )

    resolved = consumer.require(
        ExampleContract,
        service_id="provider-module.example",
        version=1,
    )
    assert resolved is implementation
    assert resolved.value() == "ok"


def test_duplicate_registration_is_fail_fast_and_contextual() -> None:
    _, provider, _ = bound_registries()
    provider.register(
        ExampleContract,
        ExampleImplementation(),
        service_id="provider-module.example",
        version=1,
    )

    with pytest.raises(DuplicateServiceRegistrationError) as error:
        provider.register(
            ExampleContract,
            ExampleImplementation(),
            service_id="provider-module.example",
            version=1,
        )

    assert error.value.service_id == "provider-module.example"
    assert error.value.requested_version == 1
    assert error.value.provider_module == "provider-module"


def test_exact_versions_can_be_registered_in_parallel() -> None:
    registry, provider, consumer = bound_registries()
    first = ExampleImplementation("v1")
    second = ExampleImplementation("v2")
    provider.register(ExampleContract, first, service_id="provider-module.example", version=1)
    provider.register(ExampleContract, second, service_id="provider-module.example", version=2)

    assert (
        consumer.require(ExampleContract, service_id="provider-module.example", version=1).value()
        == "v1"
    )
    assert (
        consumer.require(ExampleContract, service_id="provider-module.example", version=2).value()
        == "v2"
    )
    assert [(item.service_id, item.version) for item in registry.services] == [
        ("provider-module.example", 1),
        ("provider-module.example", 2),
    ]


def test_missing_required_and_incompatible_version_have_structured_errors() -> None:
    _, provider, consumer = bound_registries()
    with pytest.raises(MissingRequiredServiceError) as missing:
        consumer.require(ExampleContract, service_id="provider-module.example", version=1)
    assert missing.value.consumer_module == "consumer-module"
    assert missing.value.available_services == ()

    provider.register(
        ExampleContract,
        ExampleImplementation(),
        service_id="provider-module.example",
        version=1,
    )
    with pytest.raises(IncompatibleServiceVersionError) as incompatible:
        consumer.require(ExampleContract, service_id="provider-module.example", version=2)
    assert incompatible.value.available_versions == (1,)
    assert incompatible.value.available_services == ("provider-module.example@1",)


def test_optional_lookup_distinguishes_absent_and_incompatible_service() -> None:
    registry = ServiceRegistry()
    provider = registry.bind(manifest("provider-module"))
    consumer = registry.bind(
        manifest("consumer-module", optional={"provider-module": ">=1.0.0,<2.0.0"})
    )
    assert (
        consumer.optional(ExampleContract, service_id="provider-module.example", version=1) is None
    )

    provider.register(
        ExampleContract,
        ExampleImplementation(),
        service_id="provider-module.example",
        version=1,
    )
    assert (
        consumer.optional(ExampleContract, service_id="provider-module.example", version=1)
        is not None
    )
    with pytest.raises(IncompatibleServiceVersionError):
        consumer.optional(ExampleContract, service_id="provider-module.example", version=2)


def test_provider_ownership_and_consumer_dependencies_are_enforced() -> None:
    registry = ServiceRegistry()
    provider = registry.bind(manifest("provider-module"))
    undeclared_consumer = registry.bind(manifest("consumer-module"))

    with pytest.raises(ServiceRegistryError, match="own module namespace"):
        provider.register(
            ExampleContract,
            ExampleImplementation(),
            service_id="foreign-module.example",
            version=1,
        )
    with pytest.raises(UndeclaredServiceDependencyError):
        undeclared_consumer.require(
            ExampleContract,
            service_id="provider-module.example",
            version=1,
        )

    provider.register(
        ExampleContract,
        ExampleImplementation(),
        service_id="provider-module.example",
        version=1,
    )
    with pytest.raises(UndeclaredServiceDependencyError):
        undeclared_consumer.resolve(ExampleContract)


def test_contract_identity_is_checked_without_protocol_introspection() -> None:
    _, provider, consumer = bound_registries()
    provider.register(
        ExampleContract,
        ExampleImplementation(),
        service_id="provider-module.example",
        version=1,
    )
    with pytest.raises(ServiceContractMismatchError):
        consumer.require(OtherContract, service_id="provider-module.example", version=1)


def test_deprecation_metadata_is_validated_and_exposed() -> None:
    registry, provider, _ = bound_registries()
    provider.register(
        ExampleContract,
        ExampleImplementation(),
        service_id="provider-module.example",
        version=1,
        deprecated_since="2026-08-26",
        replacement="provider-module.example-v2",
    )
    assert registry.services[0].deprecated_since == "2026-08-26"
    assert registry.services[0].replacement == "provider-module.example-v2"

    with pytest.raises(ServiceRegistryError, match="requires deprecated_since"):
        provider.register(
            ExampleContract,
            ExampleImplementation(),
            service_id="provider-module.other",
            version=1,
            replacement="provider-module.example",
        )


def test_sealed_registry_rejects_mutation_but_keeps_lookup_available() -> None:
    registry, provider, consumer = bound_registries()
    implementation = ExampleImplementation()
    provider.register(
        ExampleContract,
        implementation,
        service_id="provider-module.example",
        version=1,
    )
    registry.seal()

    assert (
        consumer.require(ExampleContract, service_id="provider-module.example", version=1)
        is implementation
    )
    with pytest.raises(ServiceRegistrySealedError):
        provider.register(
            ExampleContract,
            ExampleImplementation(),
            service_id="provider-module.other",
            version=1,
        )


@pytest.mark.asyncio
async def test_two_fixture_modules_communicate_through_public_contract_only() -> None:
    runtime = create_module_runtime(
        enabled_module_ids=(PROVIDER.declared_id, CONSUMER.declared_id),
        discovery_providers=(FakeDiscovery((CONSUMER, PROVIDER)),),
        host_version="0.2.0",
    )
    runtime.register(FastAPI())
    consumer = runtime.registry.get(CONSUMER.declared_id).module

    assert isinstance(consumer, StatisticsFixtureModule)
    areas = await consumer.areas()
    assert areas == (
        AnalysisAreaSummary(
            area_id="flensburg",
            name="Flensburg",
            geometry={"type": "Point", "coordinates": [9.43, 54.79]},
        ),
    )
    assert is_dataclass(areas[0])


def test_runtime_wires_real_registry_and_seals_it_after_registration() -> None:
    factory = ModuleContextFactory()
    runtime = create_module_runtime(
        enabled_module_ids=(PROVIDER.declared_id,),
        discovery_providers=(FakeDiscovery((PROVIDER,)),),
        host_version="0.2.0",
        context_factory=factory,
    )
    context = runtime.registry.get(PROVIDER.declared_id).context
    assert context.services is not None
    assert factory.service_registry is not None
    assert not factory.service_registry.sealed

    runtime.register(FastAPI())
    assert factory.service_registry.sealed
    with pytest.raises(ServiceRegistrySealedError):
        context.services.register(
            AnalysisAreaQueryService,
            object(),  # type: ignore[arg-type]
            service_id=SERVICE_ID,
            version=2,
        )


def test_missing_required_service_prevents_runtime_registration() -> None:
    provider_manifest = manifest("provider-module")
    consumer_manifest = manifest("consumer-module", required={"provider-module": ">=1.0.0,<2.0.0"})

    class EmptyProvider:
        manifest = provider_manifest

        def register(self, context: ModuleContext) -> None:
            del context

    class RequiredConsumer:
        manifest = consumer_manifest

        def register(self, context: ModuleContext) -> None:
            assert context.services is not None
            context.services.require(
                ExampleContract, service_id="provider-module.example", version=1
            )

    definitions = (
        ModuleDefinition(provider_manifest, EmptyProvider, "test:provider", "provider-module"),
        ModuleDefinition(consumer_manifest, RequiredConsumer, "test:consumer", "consumer-module"),
    )
    runtime = create_module_runtime(
        enabled_module_ids=("provider-module", "consumer-module"),
        discovery_providers=(FakeDiscovery(definitions),),
        host_version="0.2.0",
    )
    with pytest.raises(ModuleRegistrationError) as error:
        runtime.register(FastAPI())
    assert isinstance(error.value.__cause__, MissingRequiredServiceError)


def test_missing_optional_service_does_not_prevent_runtime_registration() -> None:
    consumer_manifest = manifest("consumer-module", optional={"provider-module": ">=1.0.0,<2.0.0"})

    class OptionalConsumer:
        manifest = consumer_manifest

        def __init__(self) -> None:
            self.service: ExampleContract | None = None

        def register(self, context: ModuleContext) -> None:
            assert context.services is not None
            self.service = context.services.optional(
                ExampleContract, service_id="provider-module.example", version=1
            )

    definition = ModuleDefinition(
        consumer_manifest, OptionalConsumer, "test:consumer", "consumer-module"
    )
    runtime = create_module_runtime(
        enabled_module_ids=("consumer-module",),
        discovery_providers=(FakeDiscovery((definition,)),),
        host_version="0.2.0",
    )
    runtime.register(FastAPI())
    consumer = runtime.registry.get("consumer-module").module
    assert isinstance(consumer, OptionalConsumer)
    assert consumer.service is None


def test_fake_service_registry_supports_versioned_required_and_optional_lookups() -> None:
    fake = FakeServiceRegistry()
    implementation = ExampleImplementation()
    assert fake.optional(ExampleContract, service_id="provider-module.example", version=1) is None
    fake.register(
        ExampleContract,
        implementation,
        service_id="provider-module.example",
        version=1,
    )
    assert (
        fake.require(ExampleContract, service_id="provider-module.example", version=1)
        is implementation
    )
