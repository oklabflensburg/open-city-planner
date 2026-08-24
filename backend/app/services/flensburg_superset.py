import csv
import io
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings


class SupersetSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class SupersetDatasetSpec:
    id: int
    name: str
    metric: str
    dimensions: tuple[str, ...]


DATASET_SPECS = (
    SupersetDatasetSpec(
        6,
        "STK_RESULTS_Sozialatlas_01",
        "Anzahl",
        (
            "Wohnstatus",
            "Migrationshintergrund",
            "Altersgruppe",
            "Familienstand",
            "Stadtteilname",
        ),
    ),
    SupersetDatasetSpec(
        7,
        "STK_RESULTS_Haushalte_AnzahlPersonenHaushalt",
        "AnzahlHaushalte",
        ("Wohnstatus", "ZahlPersonenHaushalt", "Stadtteilname"),
    ),
    SupersetDatasetSpec(
        8,
        "STK_RESULTS_Haushalte_Migrationshintergrund",
        "AnzahlHaushalte",
        ("Wohnstatus", "Migrationshintergrund_Haushalte", "Stadtteilname"),
    ),
    SupersetDatasetSpec(
        9,
        "STK_RESULTS_Haushalte_ZahlKinderHaushalt",
        "AnzahlHaushalte",
        ("Wohnstatus", "ZahlKinderHaushalt", "Stadtteilname"),
    ),
    SupersetDatasetSpec(
        10,
        "STK_RESULTS_Haushalte_Haushaltstyp",
        "AnzahlHaushalte",
        ("Wohnstatus",),
    ),
)


class FlensburgSupersetClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        dashboard_id: str | None = None,
        timeout: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.flensburg_superset_base_url).rstrip("/")
        self.dashboard_id = dashboard_id or settings.flensburg_superset_dashboard_id
        self.timeout = timeout or settings.flensburg_superset_timeout_seconds
        self.transport = transport

    async def dashboard(self) -> dict[str, Any]:
        payload = await self._json("GET", f"/api/v1/dashboard/{self.dashboard_id}")
        result = payload.get("result")
        if not isinstance(result, dict) or result.get("dashboard_title") != "Zahlenspiegel":
            raise SupersetSourceError("Unexpected Superset dashboard response")
        return result

    async def charts(self) -> list[dict[str, Any]]:
        payload = await self._json(
            "GET", f"/api/v1/dashboard/{self.dashboard_id}/charts"
        )
        result = payload.get("result")
        if not isinstance(result, list):
            raise SupersetSourceError("Unexpected Superset chart inventory")
        return result

    async def datasets(self) -> list[dict[str, Any]]:
        payload = await self._json(
            "GET", f"/api/v1/dashboard/{self.dashboard_id}/datasets"
        )
        result = payload.get("result")
        if not isinstance(result, list):
            raise SupersetSourceError("Unexpected Superset dataset inventory")
        return result

    async def download_dataset(self, spec: SupersetDatasetSpec) -> tuple[bytes, list[dict[str, str]]]:
        query = {
            "datasource": {"id": spec.id, "type": "table"},
            "force": False,
            "queries": [
                {
                    "time_range": "No filter",
                    "granularity": "Jahr",
                    "filters": [],
                    "extras": {"time_grain_sqla": "P1Y", "having": "", "where": ""},
                    "applied_time_extras": {},
                    "columns": list(spec.dimensions),
                    "metrics": [
                        {
                            "expressionType": "SIMPLE",
                            "column": {"column_name": spec.metric},
                            "aggregate": "SUM",
                            "label": spec.metric,
                        }
                    ],
                    "orderby": [],
                    "annotation_layers": [],
                    "row_limit": 100_000,
                    "order_desc": False,
                    "is_timeseries": True,
                    "time_offsets": [],
                    "post_processing": [],
                }
            ],
            "result_format": "csv",
            "result_type": "full",
        }
        response = await self._request("POST", "/api/v1/chart/data", json=query)
        content_type = response.headers.get("content-type", "").lower()
        body = response.content
        if "text/csv" not in content_type:
            raise SupersetSourceError(f"Expected CSV for dataset {spec.id}, got {content_type}")
        if body.lstrip().lower().startswith((b"<!doctype html", b"<html")):
            raise SupersetSourceError(f"HTML received instead of CSV for dataset {spec.id}")
        try:
            text = body.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise SupersetSourceError(f"Dataset {spec.id} is not UTF-8") from exc
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;")
            reader = csv.DictReader(io.StringIO(text), dialect=dialect)
            rows = list(reader)
        except csv.Error as exc:
            raise SupersetSourceError(f"Dataset {spec.id} is not valid CSV") from exc
        expected = ["Time", *spec.dimensions, spec.metric]
        if reader.fieldnames != expected:
            raise SupersetSourceError(
                f"Schema drift in dataset {spec.id}: expected {expected}, got {reader.fieldnames}"
            )
        if not rows:
            raise SupersetSourceError(f"Dataset {spec.id} returned no rows")
        return body, rows

    async def _json(self, method: str, endpoint: str) -> dict[str, Any]:
        response = await self._request(method, endpoint)
        if "application/json" not in response.headers.get("content-type", "").lower():
            raise SupersetSourceError(f"Expected JSON from {endpoint}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SupersetSourceError(f"Invalid JSON from {endpoint}") from exc
        if not isinstance(payload, dict):
            raise SupersetSourceError(f"Unexpected JSON from {endpoint}")
        return payload

    async def _request(self, method: str, endpoint: str, **kwargs: Any) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                follow_redirects=False,
                transport=self.transport,
                headers={"User-Agent": "Stadtplaner statistics importer/1.0"},
            ) as client:
                response = await instrumented_httpx_request(
                    client,
                    method,
                    endpoint,
                    provider="flensburg_superset",
                    operation="dataset_export",
                    **kwargs,
                )
        except httpx.TimeoutException as exc:
            raise SupersetSourceError(f"Superset timeout for {endpoint}") from exc
        except httpx.HTTPError as exc:
            raise SupersetSourceError(f"Superset request failed for {endpoint}") from exc
        if response.status_code in {401, 403}:
            raise SupersetSourceError(
                f"Superset export is not publicly authorized ({response.status_code})"
            )
        if response.status_code != 200:
            raise SupersetSourceError(
                f"Superset returned HTTP {response.status_code} for {endpoint}"
            )
        return response
from app.observability.external import instrumented_httpx_request
