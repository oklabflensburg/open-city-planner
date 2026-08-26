from contextlib import asynccontextmanager
from dataclasses import replace
from importlib import resources

import httpx
import pytest
from fastapi import FastAPI

from app.modules.reference.application import (
    CreateReferenceItem,
    ReferenceItemService,
    ReferencePermissionDenied,
)
from app.modules.reference.domain import ReferenceItem
from app.modules.reference.module import DEFINITION, MANIFEST, ReferenceModule
from app.modules.reference.settings import ReferenceSettings
from app.platform.modules.discovery import FirstPartyModuleDiscovery
from app.platform.modules.runtime import resolve_module_definitions
from app.platform.modules.testing import (
    FakeEventBus,
    FakeJobRegistry,
    FakeMetrics,
    FakePermissions,
    create_test_module_context,
)


class FakeDatabase:
    @asynccontextmanager
    async def session(self):
        yield object()


def reference_context(*, allowed: set[str] | None = None):
    context = create_test_module_context(
        module_id="reference",
        module_version="1.0.0",
        settings_model=ReferenceSettings(),
    )
    return replace(
        context,
        database=FakeDatabase(),
        permissions=FakePermissions(allowed),
    )


def test_manifest_and_passive_contributions_have_one_owner() -> None:
    assert MANIFEST.id == "reference"
    assert MANIFEST.permissions == ["reference.items-write"]
    assert MANIFEST.persistence is not None
    assert MANIFEST.persistence.schema_name == "reference"
    assert DEFINITION.persistence is not None
    assert DEFINITION.persistence.metadata.tables["reference.items"].schema == "reference"
    assert DEFINITION.settings is not None
    assert DEFINITION.settings.model is ReferenceSettings
    migration = DEFINITION.persistence.migration_source
    assert migration is not None
    assert resources.files(migration.package).joinpath(migration.resource).is_dir()


def test_enabled_and_disabled_discovery_and_compatibility() -> None:
    provider = FirstPartyModuleDiscovery({"reference": DEFINITION})
    disabled = resolve_module_definitions(
        enabled_module_ids=(), discovery_providers=(provider,), host_version="0.2.0"
    )
    enabled = resolve_module_definitions(
        enabled_module_ids=("reference",),
        discovery_providers=(provider,),
        host_version="0.2.0",
    )
    assert disabled == ()
    assert [manifest.id for _, manifest in enabled] == ["reference"]

    with pytest.raises(Exception, match="requires sdk"):
        resolve_module_definitions(
            enabled_module_ids=("reference",),
            discovery_providers=(provider,),
            host_version="0.2.0",
            sdk_version="1.6.0",
        )


def test_registration_contributes_routes_event_subscriber_and_job() -> None:
    context = reference_context()
    ReferenceModule().register(context)

    registration = context.api
    assert [router.prefix for router in registration.routers] == [
        "/api/v1/modules/reference"
    ]
    events = context.events
    assert isinstance(events, FakeEventBus)
    assert [(event, handler_id, versions) for event, handler_id, versions, _ in events.subscriptions] == [
        ("reference.item-created", "reference.observe-item-created", frozenset({1}))
    ]
    scheduler = context.scheduler
    assert isinstance(scheduler, FakeJobRegistry)
    assert set(scheduler.jobs) == {"reference.count-items"}
    permission_dependencies = context.permission_dependencies
    assert permission_dependencies is not None
    assert permission_dependencies.requirements == [("reference.items-write", True)]


@pytest.mark.asyncio
async def test_write_use_case_enforces_module_permission_fail_closed() -> None:
    context = reference_context()
    service = ReferenceItemService(context)
    command = CreateReferenceItem(
        title="Nicht gespeichert",
        description="Der Permission-Check läuft vor Persistence und Event.",
        longitude=9.43,
        latitude=54.78,
    )

    with pytest.raises(ReferencePermissionDenied):
        await service.create_item(command, principal_id="user-1")

    permissions = context.permissions
    assert isinstance(permissions, FakePermissions)
    assert permissions.checks == [("reference.items-write", "user-1", None)]


@pytest.mark.asyncio
async def test_permitted_create_persists_and_publishes_event(monkeypatch) -> None:
    stored = []

    class Repository:
        def __init__(self, _session) -> None:
            pass

        def add(self, item) -> None:
            stored.append(item)

    monkeypatch.setattr(
        "app.modules.reference.application.service.SqlAlchemyReferenceItemRepository",
        Repository,
    )
    context = reference_context(allowed={"reference.items-write"})
    item = await ReferenceItemService(context).create_item(
        CreateReferenceItem(
            title="Erlaubter Marker",
            description="Test",
            longitude=9.43,
            latitude=54.78,
        ),
        principal_id="user-1",
    )

    assert stored == [item]
    events = context.events
    assert isinstance(events, FakeEventBus)
    assert events.queued[0].event_name == "reference.item-created"
    assert events.queued[0].payload["item_id"] == item.id


@pytest.mark.asyncio
async def test_subscriber_and_job_can_execute(monkeypatch) -> None:
    class Repository:
        def __init__(self, _session) -> None:
            pass

        async def count(self) -> int:
            return 2

    monkeypatch.setattr(
        "app.modules.reference.application.service.SqlAlchemyReferenceItemRepository",
        Repository,
    )
    context = reference_context()
    ReferenceModule().register(context)
    events = context.events
    scheduler = context.scheduler
    assert isinstance(events, FakeEventBus)
    assert isinstance(scheduler, FakeJobRegistry)

    from app.modules.reference.domain import ReferenceItemCreated
    from app.platform.modules.sdk import event_envelope

    await events.subscriptions[0][3](
        event_envelope(ReferenceItemCreated(item_id="item-1", title="Marker"))
    )
    metrics = context.observability.metrics
    assert isinstance(metrics, FakeMetrics)
    assert metrics.increments == [("items-created", 1, {})]
    assert await scheduler.run("reference.count-items", context) == 2
    assert metrics.observations == [("items-total", 2.0, {})]


@pytest.mark.asyncio
async def test_enabled_api_creates_and_lists_items(monkeypatch) -> None:
    stored: list[ReferenceItem] = []

    class Repository:
        def __init__(self, _session) -> None:
            pass

        async def list(self, *, limit: int) -> tuple[ReferenceItem, ...]:
            return tuple(stored[:limit])

        def add(self, item: ReferenceItem) -> None:
            stored.append(item)

    monkeypatch.setattr(
        "app.modules.reference.application.service.SqlAlchemyReferenceItemRepository",
        Repository,
    )
    context = reference_context(allowed={"reference.items-write"})
    ReferenceModule().register(context)
    app = FastAPI()
    for contribution in context.api.routers:
        app.include_router(contribution.router, prefix=contribution.prefix)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/modules/reference/items",
            json={
                "title": "API-Marker",
                "description": "End-to-End im Modul",
                "longitude": 9.43,
                "latitude": 54.78,
            },
        )
        listed = await client.get("/api/v1/modules/reference/items")

    assert created.status_code == 201
    assert created.json()["title"] == "API-Marker"
    assert listed.status_code == 200
    assert [item["title"] for item in listed.json()] == ["API-Marker"]


def test_reference_settings_are_defaulted_typed_and_overridable() -> None:
    assert ReferenceSettings().max_items == 100
    overridden = ReferenceSettings.model_validate(
        {"max_items": "25", "job_interval_seconds": "600"}
    )
    assert overridden.max_items == 25
    assert overridden.job_interval_seconds == 600
