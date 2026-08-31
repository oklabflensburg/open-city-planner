import json
from pathlib import Path

import pytest

from app.platform.modules.dependency_graph import resolve_module_order
from app.platform.modules.errors import ModuleCompatibilityError, ModuleDependencyCycleError
from app.platform.modules.manifest import parse_manifest, validate_manifest
from app.platform.modules.testing import (
    FakeCacheGenerations,
    FakeServiceRegistry,
    ModuleTestHost,
)
from tests.fixtures.service_modules.analysis_areas.module import DEFINITION

FIXTURES = Path(__file__).parent / "fixtures/module_contracts"


def load_fixture(name: str):
    return parse_manifest(json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def test_module_test_host_registers_example_without_infrastructure() -> None:
    host = ModuleTestHost(DEFINITION)

    context = host.register()

    assert context.database is None
    assert context.module_id == "analysis-areas-fixture"
    assert isinstance(context.services, FakeServiceRegistry)
    assert context.services.sealed is True


@pytest.mark.asyncio
async def test_module_test_host_exposes_mutable_cache_generations() -> None:
    host = ModuleTestHost(DEFINITION)

    context = host.register()
    assert isinstance(context.cache_generations, FakeCacheGenerations)

    await context.cache_generations.bump(object(), ("fixture-resource",))

    assert await context.cache_generations.current(object(), "fixture-resource") == 2


def test_module_test_host_closes_registration_after_bootstrap() -> None:
    host = ModuleTestHost(DEFINITION)
    host.register()

    with pytest.raises(RuntimeError, match="closed"):
        host.context.lifecycle.add_lifecycle(startup=_noop)


async def _noop() -> None:
    return None


def test_broken_cycle_fixture_is_rejected() -> None:
    with pytest.raises(ModuleDependencyCycleError):
        resolve_module_order([load_fixture("cycle-a.json"), load_fixture("cycle-b.json")])


def test_incompatible_sdk_fixture_is_rejected() -> None:
    with pytest.raises(ModuleCompatibilityError):
        validate_manifest(
            load_fixture("incompatible-sdk.json"),
            host_version="0.2.0",
            sdk_version="1.3.0",
        )
