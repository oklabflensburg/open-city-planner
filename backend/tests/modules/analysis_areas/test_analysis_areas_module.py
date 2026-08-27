from contextlib import asynccontextmanager
from dataclasses import replace

import pytest

from app.modules.analysis_areas.contracts import (
    SERVICE_ID,
    SERVICE_VERSION,
    AnalysisAreaQueryService,
)
from app.modules.analysis_areas.module import (
    DEFINITION,
    MANIFEST,
    AnalysisAreasModule,
)
from app.platform.modules.discovery import FirstPartyModuleDiscovery
from app.platform.modules.persistence import build_persistence_registry
from app.platform.modules.runtime import resolve_module_definitions
from app.platform.modules.testing import FakeServiceRegistry, create_test_module_context


class FakeDatabase:
    @asynccontextmanager
    async def session(self):
        yield object()


def module_context():
    return replace(
        create_test_module_context(
            module_id="analysis-areas",
            module_version="1.0.0",
        ),
        database=FakeDatabase(),
    )


def test_manifest_router_service_and_adopted_table_have_one_owner() -> None:
    assert MANIFEST.id == "analysis-areas"
    assert MANIFEST.version == "1.0.0"
    assert MANIFEST.persistence is not None
    assert MANIFEST.persistence.schema_name == "analysis_areas"
    assert DEFINITION.persistence is not None
    assert DEFINITION.persistence.adopted_tables == frozenset({"analysis_areas"})
    assert set(DEFINITION.persistence.metadata.tables) == {"analysis_areas"}

    context = module_context()
    AnalysisAreasModule().register(context)
    assert [item.prefix for item in context.api.routers] == ["/api/v1"]
    services = context.services
    assert isinstance(services, FakeServiceRegistry)
    assert (SERVICE_ID, SERVICE_VERSION) in services.versioned_services
    contract, _ = services.versioned_services[(SERVICE_ID, SERVICE_VERSION)]
    assert contract is AnalysisAreaQueryService


def test_enabled_disabled_discovery_and_persistence_adoption() -> None:
    provider = FirstPartyModuleDiscovery({"analysis-areas": DEFINITION})
    disabled = resolve_module_definitions(
        enabled_module_ids=(),
        discovery_providers=(provider,),
        host_version="0.2.0",
    )
    enabled = resolve_module_definitions(
        enabled_module_ids=("analysis-areas",),
        discovery_providers=(provider,),
        host_version="0.2.0",
    )
    assert disabled == ()
    assert [manifest.id for _, manifest in enabled] == ["analysis-areas"]
    persistence = build_persistence_registry(enabled, include_legacy=False).contributions
    assert persistence[0].adopted_tables == frozenset({"analysis_areas"})
    assert persistence[0].migration_source is None


@pytest.mark.asyncio
async def test_public_query_service_materializes_lookup_without_session_leak(monkeypatch) -> None:
    from app.modules.analysis_areas.api.schemas import AnalysisAreaRead
    from app.modules.analysis_areas.application import query_service

    area = AnalysisAreaRead(
        id="5d91f92e-aaf8-4933-9704-a93cc6466ac5",
        slug="altstadt-1",
        name="Altstadt",
        area_type="DISTRICT",
        area_m2=10.0,
        source="OSM",
        updated_at="2026-08-26T00:00:00Z",
    )

    async def fake_list(_session, area_type=None, parent_id=None):
        assert area_type == "DISTRICT"
        assert parent_id is None
        return [area]

    monkeypatch.setattr(query_service, "list_areas", fake_list)
    service = query_service.SqlAnalysisAreaQueryService(FakeDatabase())
    result = await service.list_areas(area_type="DISTRICT")

    assert result[0].slug == "altstadt-1"
    assert result[0].parent_id is None
