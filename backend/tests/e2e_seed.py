"""Deterministische Minimaldaten für die browserbasierten End-to-End-Tests."""

import asyncio
import hashlib
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from geoalchemy2.elements import WKTElement

from app.auth.passwords import hash_password
from app.db.session import AsyncSessionLocal
from app.models.statistics import StatisticalDataset, StatisticalMetric, StatisticalObservation
from app.models.user import User
from app.models.user_polygon import UserPolygon
from app.modules.analysis_areas.persistence.models import AnalysisArea, PolygonAnalysisArea

E2E_PASSWORD = "playwright-test-password"


def area(
    *,
    slug: str,
    name: str,
    area_type: str,
    bounds: tuple[float, float, float, float],
    osm_id: int,
    parent_id: int | None = None,
    wikidata_id: str | None = None,
    wikipedia_title: str | None = None,
) -> AnalysisArea:
    west, south, east, north = bounds
    geometry = (
        f"MULTIPOLYGON((({west} {south},{east} {south},{east} {north},"
        f"{west} {north},{west} {south})))"
    )
    return AnalysisArea(
        uuid=uuid.uuid5(uuid.NAMESPACE_URL, f"stadtplaner-e2e:{slug}"),
        slug=slug,
        name=name,
        area_type=area_type,
        parent_id=parent_id,
        geometry=WKTElement(geometry, srid=4326),
        centroid=WKTElement(f"POINT({(west + east) / 2} {(south + north) / 2})", srid=4326),
        area_m2=1_000_000,
        source="OSM",
        source_osm_type="relation",
        source_osm_id=osm_id,
        source_osm_wikidata=wikidata_id,
        source_osm_wikipedia=(f"de:{wikipedia_title}" if wikipedia_title else None),
        wikidata_id=wikidata_id,
        wikipedia_title=wikipedia_title,
        wikidata_match_source="OSM_WIKIDATA" if wikidata_id else None,
        wikidata_match_status="VERIFIED" if wikidata_id else "NOT_FOUND",
        wikidata_match_confidence=1.0 if wikidata_id else None,
        wikidata_verified=bool(wikidata_id),
    )


def observation(
    metric_id: int,
    area_id: int,
    year: int,
    value: int,
    source_area_id: str,
) -> StatisticalObservation:
    fingerprint = f"{metric_id}:{area_id}:{year}:{value}"
    return StatisticalObservation(
        metric_id=metric_id,
        analysis_area_id=area_id,
        period_type="YEAR",
        period_start=date(year, 1, 1),
        period_end=date(year, 12, 31),
        value_numeric=Decimal(value),
        source_area_id=source_area_id,
        source_row_hash=hashlib.sha256(fingerprint.encode()).hexdigest(),
        is_calculated=False,
    )


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        session.add_all(
            [
                User(
                    id=uuid.UUID("33333333-3333-4333-8333-333333333333"),
                    email="account@example.org",
                    password_hash=hash_password(E2E_PASSWORD),
                    first_name="Account",
                    last_name="Owner",
                    display_name="Account Owner",
                    is_active=True,
                    is_verified=True,
                    roles=[],
                ),
                User(
                    id=uuid.UUID("22222222-2222-4222-8222-222222222222"),
                    email="admin@example.org",
                    password_hash=hash_password(E2E_PASSWORD),
                    first_name="Ada",
                    last_name="Admin",
                    display_name="Ada Admin",
                    is_active=True,
                    is_verified=True,
                    is_superuser=True,
                    roles=[],
                ),
            ]
        )

        flensburg = area(
            slug="flensburg-27020",
            name="Flensburg",
            area_type="MUNICIPALITY",
            bounds=(9.35, 54.75, 9.55, 54.85),
            osm_id=27020,
            wikidata_id="Q3798",
            wikipedia_title="Flensburg",
        )
        session.add(flensburg)
        await session.flush()

        altstadt = area(
            slug="altstadt-15630273",
            name="Altstadt",
            area_type="DISTRICT",
            bounds=(9.42, 54.78, 9.46, 54.81),
            osm_id=15630273,
            parent_id=flensburg.id,
            wikidata_id="Q16064416",
            wikipedia_title="Altstadt_(Flensburg)",
        )
        session.add(altstadt)
        await session.flush()

        for quarter in (
            area(
                slug="achter-de-moehl-15655762",
                name="Achter de Möhl",
                area_type="QUARTER",
                bounds=(9.425, 54.785, 9.435, 54.795),
                osm_id=15655762,
                parent_id=altstadt.id,
                wikidata_id="Q1420075",
                wikipedia_title="Achter_de_Möhl",
            ),
            area(
                slug="kreuz-15652249",
                name="Kreuz",
                area_type="QUARTER",
                bounds=(9.435, 54.785, 9.445, 54.795),
                osm_id=15652249,
                parent_id=altstadt.id,
            ),
            area(
                slug="nordertor-15651154",
                name="Nordertor",
                area_type="QUARTER",
                bounds=(9.425, 54.795, 9.435, 54.805),
                osm_id=15651154,
                parent_id=altstadt.id,
            ),
        ):
            session.add(quarter)

        polygon = UserPolygon(
            uuid=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
            name="E2E-Testfläche",
            slug="e2e-testflaeche",
            description="Deterministische Testfläche für die Browser-Tests.",
            address_display_name="E2E-Testfläche, Flensburg",
            address_city="Flensburg",
            address_lookup_status="resolved",
            occupancy_status="UNKNOWN",
            occupancy_source="UNKNOWN",
            business_structure="UNKNOWN",
            category="custom",
            geometry=WKTElement(
                "POLYGON((9.428 54.788,9.432 54.788,9.432 54.792,9.428 54.792,9.428 54.788))",
                srid=4326,
            ),
            properties={"source": "e2e"},
        )
        session.add(polygon)
        await session.flush()
        session.add(
            PolygonAnalysisArea(
                polygon_id=polygon.id,
                analysis_area_id=altstadt.id,
                assignment_type="POINT_ON_SURFACE",
                overlap_ratio=1.0,
            )
        )

        imported_at = datetime(2026, 1, 1, tzinfo=UTC)
        dataset = StatisticalDataset(
            source="FLENSBURG_STATISTICS",
            external_dataset_id="e2e-population",
            name="Stadt Flensburg – Zahlenspiegel",
            description="Reproduzierbare Beispieldaten für die E2E-Tests.",
            source_url="https://www.flensburg.de/",
            license="Datenlizenz Deutschland – Namensnennung – Version 2.0",
            update_frequency="YEARLY",
            last_import_at=imported_at,
            source_updated_at=imported_at,
        )
        session.add(dataset)
        await session.flush()
        metric = StatisticalMetric(
            dataset_id=dataset.id,
            key="population",
            name="Bevölkerung",
            unit="Personen",
            value_type="numeric",
            category="Bevölkerung",
            aggregation_method="SUM",
            public=True,
        )
        session.add(metric)
        await session.flush()
        session.add_all(
            [
                observation(metric.id, flensburg.id, 2020, 90_164, "flensburg"),
                observation(metric.id, flensburg.id, 2025, 98_040, "flensburg"),
                observation(metric.id, altstadt.id, 2020, 3_412, "altstadt"),
                observation(metric.id, altstadt.id, 2025, 3_657, "altstadt"),
            ]
        )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
