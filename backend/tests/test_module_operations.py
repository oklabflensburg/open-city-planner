import logging
from dataclasses import replace

import httpx
import pytest
from fastapi import FastAPI

from app.api.admin import router as admin_router
from app.auth.dependencies import require_superuser
from app.platform.modules import (
    FirstPartyModuleDiscovery,
    JobDefinition,
    ModuleContext,
    ModuleDefinition,
    create_module_runtime,
    parse_manifest,
)
from app.platform.modules.operations import safe_module_origin
from tests.test_module_runtime import definition, manifest_data, runtime_for


def test_real_enabled_analysis_areas_module_is_visible_with_manifest_capabilities() -> None:
    runtime = create_module_runtime(
        enabled_module_ids=("analysis-areas",),
        discovery_providers=(FirstPartyModuleDiscovery(),),
        host_version="0.2.0",
    )

    module = runtime.operational_status.modules[0]
    assert module.id == "analysis-areas"
    assert module.version == "1.0.0"
    assert module.origin == "built-in"
    assert module.capabilities == (
        "analysis-areas.public-api",
        "analysis-areas.lookup",
        "analysis-areas.geojson",
    )


def test_status_projects_only_enabled_records_and_validated_dependencies() -> None:
    runtime = runtime_for(
        [
            definition("base-module", capabilities=["base-module.read"]),
            definition(
                "consumer",
                required={"base-module": ">=1.0.0,<2.0.0"},
                optional={"disabled-module": ">=1.0.0,<2.0.0"},
                capabilities=["consumer.read"],
            ),
            definition("disabled-module"),
        ],
        enabled=("consumer", "base-module"),
    )

    payload = runtime.operational_status.model_dump(mode="json")

    assert [module["id"] for module in payload["modules"]] == ["base-module", "consumer"]
    assert payload["modules"][0] == {
        "id": "base-module",
        "version": "1.0.0",
        "status": "loaded",
        "enabled": True,
        "registered": False,
        "capabilities": ["base-module.read"],
        "dependencies": [],
        "origin": "unknown",
        "job_count": 0,
    }
    assert payload["modules"][1]["dependencies"] == [
        {
            "id": "base-module",
            "requirement": ">=1.0.0,<2.0.0",
            "resolved": "1.0.0",
            "optional": False,
            "compatible": True,
        }
    ]


@pytest.mark.asyncio
async def test_status_is_derived_from_registration_and_running_flags() -> None:
    runtime = runtime_for([definition("example-module")])
    assert runtime.operational_status.modules[0].status == "loaded"

    runtime.register(FastAPI())
    registered = runtime.operational_status.modules[0]
    assert registered.status == "registered"
    assert registered.registered is True

    await runtime.startup()
    assert runtime.operational_status.modules[0].status == "running"

    await runtime.shutdown()
    assert runtime.operational_status.modules[0].status == "registered"


@pytest.mark.asyncio
async def test_lifecycle_logs_keep_bounded_module_fields(caplog: pytest.LogCaptureFixture) -> None:
    runtime = runtime_for([definition("example-module")])

    with caplog.at_level(logging.INFO, logger="app.platform.modules.runtime"):
        runtime.register(FastAPI())
        await runtime.startup()

    lifecycle = [
        record
        for record in caplog.records
        if getattr(record, "module_id", None) == "example-module"
    ]
    assert [record.getMessage() for record in lifecycle] == [
        "Module registration started",
        "Module registration completed",
        "Module startup started",
        "Module startup completed",
    ]
    assert {record.module_version for record in lifecycle} == {"1.0.0"}
    assert {record.module_phase for record in lifecycle} == {"registration", "startup"}


def test_status_counts_only_jobs_registered_for_each_module() -> None:
    manifest = parse_manifest(manifest_data("job-module"))

    class JobModule:
        def __init__(self) -> None:
            self.manifest = manifest

        def register(self, context: ModuleContext) -> None:
            assert context.scheduler is not None

            async def refresh(_context: ModuleContext) -> None:
                return None

            context.scheduler.register(JobDefinition(job_id="refresh", handler=refresh))

    runtime = runtime_for(
        [ModuleDefinition(manifest, JobModule, "app.modules.job_module.module", "job-module")]
    )
    runtime.register(FastAPI())

    module = runtime.operational_status.modules[0]
    assert module.job_count == 1
    assert module.origin == "built-in"


@pytest.mark.parametrize(
    ("origin", "safe"),
    [
        ("app.modules.reference.module", "built-in"),
        ("entry-point:reference=package:definition", "entry-point"),
        ("/home/operator/project/module.py", "unknown"),
    ],
)
def test_origin_is_reduced_to_a_safe_bounded_category(origin: str, safe: str) -> None:
    assert safe_module_origin(origin) == safe


@pytest.mark.asyncio
async def test_operational_endpoint_requires_admin_and_never_exposes_secrets() -> None:
    unsafe_definition = replace(
        definition("safe-module", capabilities=["safe-module.read"]),
        origin="entry-point:safe-module=/home/alice/token=top-secret",
    )
    runtime = runtime_for([unsafe_definition])
    runtime.registry.records[0].module.password = "module-password"  # type: ignore[attr-defined]
    runtime.register(FastAPI())

    app = FastAPI()
    app.state.module_runtime = runtime
    app.include_router(admin_router, prefix="/api/v1")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        unauthenticated = await client.get("/api/v1/admin/modules/status")

    assert unauthenticated.status_code == 401

    async def allow_superuser() -> object:
        return object()

    app.dependency_overrides[require_superuser] = allow_superuser
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/admin/modules/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["modules"][0]["origin"] == "entry-point"
    serialized = response.text
    for secret in ("/home/alice", "top-secret", "module-password", "password"):
        assert secret not in serialized
