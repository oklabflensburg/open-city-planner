from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.main import app
from app.models.statistics import StatisticalImportRun
from app.services.flensburg_statistics_import import (
    AREA_MAPPING,
    _mark_import_failed,
    normalize_rows,
    observation_change,
    parse_value,
    validate_source_areas,
)
from app.services.flensburg_superset import (
    DATASET_SPECS,
    FlensburgSupersetClient,
    SupersetSourceError,
)


def client_for(handler: httpx.AsyncBaseTransport) -> FlensburgSupersetClient:
    return FlensburgSupersetClient(base_url="https://example.test", transport=handler)


@pytest.mark.asyncio
async def test_superset_client_downloads_utf8_bom_semicolon_csv() -> None:
    spec = DATASET_SPECS[1]

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/chart/data"
        payload = __import__("json").loads(request.content)
        assert payload["datasource"] == {"id": 7, "type": "table"}
        content = (
            "\ufeffTime;Wohnstatus;ZahlPersonenHaushalt;Stadtteilname;AnzahlHaushalte\n"
            "2025-01-01;Hauptwohnung;1;Südstadt;123\n"
        ).encode()
        return httpx.Response(200, headers={"content-type": "text/csv; charset=utf-8"}, content=content)

    body, rows = await client_for(httpx.MockTransport(handler)).download_dataset(spec)
    assert body.startswith(b"\xef\xbb\xbf")
    assert rows == [{
        "Time": "2025-01-01",
        "Wohnstatus": "Hauptwohnung",
        "ZahlPersonenHaushalt": "1",
        "Stadtteilname": "Südstadt",
        "AnzahlHaushalte": "123",
    }]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 404])
async def test_superset_client_rejects_http_errors(status: int) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"message": "no"})

    with pytest.raises(SupersetSourceError, match=str(status)):
        await client_for(httpx.MockTransport(handler)).download_dataset(DATASET_SPECS[0])


@pytest.mark.asyncio
async def test_superset_client_rejects_html_instead_of_csv() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<html>login</html>")

    with pytest.raises(SupersetSourceError, match="Expected CSV"):
        await client_for(httpx.MockTransport(handler)).download_dataset(DATASET_SPECS[0])


@pytest.mark.asyncio
async def test_superset_client_rejects_timeout() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(SupersetSourceError, match="timeout"):
        await client_for(httpx.MockTransport(handler)).download_dataset(DATASET_SPECS[0])


@pytest.mark.asyncio
async def test_superset_client_rejects_invalid_encoding_and_schema() -> None:
    responses = iter([
        httpx.Response(200, headers={"content-type": "text/csv"}, content=b"\xff\xfe"),
        httpx.Response(200, headers={"content-type": "text/csv"}, text="wrong,columns\n1,2\n"),
    ])

    async def handler(_request: httpx.Request) -> httpx.Response:
        return next(responses)

    client = client_for(httpx.MockTransport(handler))
    with pytest.raises(SupersetSourceError, match="UTF-8"):
        await client.download_dataset(DATASET_SPECS[0])
    with pytest.raises(SupersetSourceError, match="Schema drift"):
        await client.download_dataset(DATASET_SPECS[0])


def test_german_numbers_and_suppressed_values_are_normalized() -> None:
    assert parse_value("1.234,56") == Decimal("1234.56")
    assert parse_value("12,4 %") == Decimal("12.4")
    for value in ("-", ".", "k.A.", "keine Angabe", ""):
        assert parse_value(value) is None
    with pytest.raises(ValueError, match="Invalid statistical value"):
        parse_value("twelve")


def test_normalization_aggregates_duplicate_rows_and_never_creates_quarters() -> None:
    district_names = [
        name for name, area_type in AREA_MAPPING.values() if area_type == "DISTRICT"
    ]
    rows = []
    for name in district_names:
        rows.extend([
            {"Time": "2025-01-01", "Wohnstatus": "Hauptwohnung", "ZahlPersonenHaushalt": "1", "Stadtteilname": name, "AnzahlHaushalte": "10"},
            {"Time": "2025-01-01", "Wohnstatus": "Hauptwohnung", "ZahlPersonenHaushalt": "2", "Stadtteilname": name, "AnzahlHaushalte": "5"},
        ])
    values, names = normalize_rows({7: rows})
    assert names == set(district_names)
    assert values[("households", "Altstadt", 2025)] == Decimal(15)
    assert values[("households", "Flensburg", 2025)] == Decimal(195)
    assert all(area in {*district_names, "Flensburg"} for _metric, area, _year in values)


def test_suppressed_component_keeps_aggregate_suppressed() -> None:
    values, _ = normalize_rows({7: [
        {"Time": "2025-01-01", "Wohnstatus": "Hauptwohnung", "ZahlPersonenHaushalt": "1", "Stadtteilname": "Altstadt", "AnzahlHaushalte": "10"},
        {"Time": "2025-01-01", "Wohnstatus": "Hauptwohnung", "ZahlPersonenHaushalt": "2", "Stadtteilname": "Altstadt", "AnzahlHaushalte": "-"},
    ]})
    assert values[("households", "Altstadt", 2025)] is None


def test_import_classifies_new_unchanged_and_updated_observations() -> None:
    assert observation_change(None, "new-hash") == "new"
    assert observation_change("same-hash", "same-hash") == "unchanged"
    assert observation_change("old-hash", "new-hash") == "updated"


def test_area_validation_rejects_missing_and_unknown_areas() -> None:
    expected = {
        name for name, area_type in AREA_MAPPING.values() if area_type == "DISTRICT"
    }
    assert validate_source_areas(expected) == ([], [])
    with pytest.raises(ValueError, match="unmapped=.*Unbekannt.*missing=.*Altstadt"):
        validate_source_areas(expected - {"Altstadt"} | {"Unbekannt"})


def test_unknown_statistical_dimension_aborts_normalization() -> None:
    row = {
        "Time": "2025-01-01",
        "Wohnstatus": "Hauptwohnung",
        "Migrationshintergrund": "Deutsch",
        "Altersgruppe": "neue Altersgruppe",
        "Familienstand": "ledig",
        "Stadtteilname": "Altstadt",
        "Anzahl": "10",
    }
    with pytest.raises(ValueError, match="Unknown statistical dimension"):
        normalize_rows({6: [row]})


@pytest.mark.asyncio
async def test_failed_import_run_is_recorded_by_stable_id() -> None:
    failed_run = SimpleNamespace(status="RUNNING", finished_at=None, error_message=None)
    session = AsyncMock()
    session.get.return_value = failed_run

    await _mark_import_failed(session, 42, ValueError("mapping unavailable"))

    session.rollback.assert_awaited_once()
    session.get.assert_awaited_once_with(StatisticalImportRun, 42)
    session.commit.assert_awaited_once()
    assert failed_run.status == "FAILED"
    assert failed_run.finished_at is not None
    assert failed_run.error_message == "mapping unavailable"


def test_openapi_documents_statistics_endpoints() -> None:
    paths = app.openapi()["paths"]
    assert "/api/v1/analysis-areas/by-slug/{slug}/statistics" in paths
    assert "/api/v1/analysis-areas/by-slug/{slug}/statistics/{metric_key}" in paths
    assert "/api/v1/data-sources/status" in paths
    assert "Statistics" in paths["/api/v1/analysis-areas/by-slug/{slug}/statistics"]["get"]["tags"]
