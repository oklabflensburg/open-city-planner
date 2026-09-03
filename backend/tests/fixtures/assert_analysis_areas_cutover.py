"""Assertions for the installed Analysis Areas release lifecycle."""

import asyncio
import os
import sys
from pathlib import Path

import httpx
from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.platform.modules.installer import read_modules_lock

VERSION = "1.5.2"
DIGEST = "835a2745da15cdc17587324e451ea1b922ae0628738603c7a061d62407d08d58"
SOURCE_COMMIT = "89103403382ecd4fee992611f1011b58a0562d98"


def analysis_entry():
    root = Path(os.environ["OCP_MODULE_INSTALL_ROOT"])
    entries = {entry.id: entry for entry in read_modules_lock(root / "modules.lock").modules}
    assert set(entries) == {"analysis-areas", "statistics"}
    entry = entries["analysis-areas"]
    assert entry.version == VERSION
    assert entry.artifact.sha256 == DIGEST
    assert entry.publisher == "oklabflensburg"
    assert entry.provenance.source_repository == (
        "https://github.com/oklabflensburg/ocp-module-analysis-areas"
    )
    assert entry.provenance.source_tag == "v1.5.2"
    assert entry.provenance.source_commit == SOURCE_COMMIT
    assert entry.backend.present and entry.frontend.present
    return entry


async def row_count() -> int:
    async with AsyncSessionLocal() as session:
        return int(await session.scalar(text("SELECT count(*) FROM analysis_areas")) or 0)


async def prove_enabled() -> None:
    from app.main import app, module_runtime

    assert await row_count() == 2
    assert set(module_runtime.module_ids) == {"analysis-areas", "statistics"}
    status = {item.id: item for item in module_runtime.operational_status.modules}
    assert status["analysis-areas"].version == VERSION
    assert status["analysis-areas"].job_count == 1
    assert "analysis-areas.wikidata-maintenance" in status["analysis-areas"].capabilities
    paths = set(app.openapi()["paths"])
    assert {
        "/api/v1/analysis-areas",
        "/api/v1/analysis-areas/geojson",
        "/api/v1/analysis-areas/sitemap",
        "/api/v1/analysis-areas/by-slug/{slug}",
        "/api/v1/analysis-areas/by-slug/{slug}/analytics",
        "/api/v1/analysis-areas/{area_id}/analytics",
        "/api/v1/analysis-areas/by-slug/{slug}/comparison",
        "/api/v1/analysis-areas/by-slug/{slug}/statistics",
    } <= paths
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        for endpoint in (
            "/api/v1/analysis-areas",
            "/api/v1/analysis-areas/geojson",
            "/api/v1/analysis-areas/sitemap",
            "/api/v1/analysis-areas/by-slug/innenstadt-test",
            "/api/v1/analysis-areas/by-slug/innenstadt-test/analytics",
            "/api/v1/analysis-areas/by-slug/innenstadt-test/comparison",
            "/api/v1/analysis-areas/by-slug/innenstadt-test/polygons",
        ):
            response = await client.get(endpoint)
            assert response.status_code == 200, (endpoint, response.text)
        detail = (
            await client.get("/api/v1/analysis-areas/by-slug/innenstadt-test")
        ).json()
        assert detail["external_links"]["wikidata"]["id"] == "Q12345"
        assert detail["external_links"]["wikipedia"]["title"] == "Flensburg-Altstadt"
        assert detail["bbox"] == [9.42, 54.78, 9.45, 54.8]

        analytics_response = await client.get(
            "/api/v1/analysis-areas/11111111-1111-4111-8111-222222222222/analytics"
        )
        assert analytics_response.status_code == 200, analytics_response.text
        analytics = analytics_response.json()
        assert analytics["area"]["id"] == "11111111-1111-4111-8111-222222222222"
        assert analytics["poi_count"] == 1
        assert {item["category"]: item["count"] for item in analytics["poi_categories"]} == {
            "cafe": 1
        }

        statistics_response = await client.get(
            "/api/v1/analysis-areas/by-slug/innenstadt-test/statistics"
        )
        assert statistics_response.status_code == 200, statistics_response.text
        assert statistics_response.json()["latest"]


def prove_disabled(entry, *, migrated: bool) -> None:
    assert entry.enabled is False
    from app.main import app, module_runtime

    assert "analysis-areas" not in module_runtime.module_ids
    assert not any(
        path.startswith("/api/v1/analysis-areas") for path in app.openapi()["paths"]
    )
    if migrated:
        assert asyncio.run(row_count()) == 2


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {
        "disabled",
        "enabled",
        "disabled-after-migration",
    }:
        raise SystemExit("usage: assert_analysis_areas_cutover.py STATE")
    state = sys.argv[1]
    entry = analysis_entry()
    if state == "enabled":
        assert entry.enabled is True
        asyncio.run(prove_enabled())
    else:
        prove_disabled(entry, migrated=state == "disabled-after-migration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
