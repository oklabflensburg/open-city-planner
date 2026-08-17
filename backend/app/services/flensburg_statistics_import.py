import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_audit_log import AdminAuditLog
from app.models.analysis_area import AnalysisArea
from app.models.statistics import (
    ExternalAreaMapping,
    StatisticalDataset,
    StatisticalImportRun,
    StatisticalMetric,
    StatisticalObservation,
)
from app.services.cache_versions import bump_cache_versions
from app.services.flensburg_superset import DATASET_SPECS, FlensburgSupersetClient
from app.services.notification_policy import DomainEvent, NotificationEventType
from app.services.notifications import (
    notify_superusers,
    notify_users,
    publish_notifications,
    subscription_recipient_ids,
)
from app.services.social_publishing import enqueue_statistics_summary

logger = logging.getLogger(__name__)

SOURCE = "FLENSBURG_STATISTICS"
DASHBOARD_URL = (
    "https://superset.flensburg.de/superset/dashboard/3b53ff0b-6e8c-435e-83f6-666f8a7cc158/"
)
LICENSE = "Datenlizenz Deutschland – Zero – Version 2.0"

# Official district numbers published by the City of Flensburg. Superset itself
# currently exports only the names; this reviewed mapping is therefore explicit.
AREA_MAPPING = {
    "00": ("Flensburg", "MUNICIPALITY"),
    "01": ("Altstadt", "DISTRICT"),
    "02": ("Neustadt", "DISTRICT"),
    "03": ("Nordstadt", "DISTRICT"),
    "04": ("Westliche Höhe", "DISTRICT"),
    "05": ("Friesischer Berg", "DISTRICT"),
    "06": ("Weiche", "DISTRICT"),
    "07": ("Südstadt", "DISTRICT"),
    "08": ("Sandberg", "DISTRICT"),
    "09": ("Jürgensby", "DISTRICT"),
    "10": ("Fruerlund", "DISTRICT"),
    "11": ("Mürwik", "DISTRICT"),
    "12": ("Engelsby", "DISTRICT"),
    "13": ("Tarup", "DISTRICT"),
}


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    name: str
    category: str
    dataset_id: int
    unit: str = "persons"
    description: str | None = None


METRICS = (
    MetricDefinition("population", "Bevölkerung", "Bevölkerung", 6),
    MetricDefinition("population_non_german", "Bevölkerung nicht deutsch", "Bevölkerung", 6),
    MetricDefinition("population_age_0_17", "Bevölkerung unter 18", "Altersstruktur", 6),
    MetricDefinition("population_age_18_64", "Bevölkerung 18 bis unter 65", "Altersstruktur", 6),
    MetricDefinition("population_age_65_plus", "Bevölkerung 65 plus", "Altersstruktur", 6),
    MetricDefinition("population_marital_single", "Ledig", "Familienstand", 6),
    MetricDefinition("population_marital_married", "Verheiratet", "Familienstand", 6),
    MetricDefinition("population_marital_divorced", "Geschieden", "Familienstand", 6),
    MetricDefinition("population_marital_widowed", "Verwitwet", "Familienstand", 6),
    MetricDefinition("population_marital_other", "Sonstiger Familienstand", "Familienstand", 6),
    MetricDefinition("population_marital_unknown", "Familienstand ohne Angabe", "Familienstand", 6),
    MetricDefinition("households", "Haushalte", "Haushalte", 7, "households"),
    MetricDefinition(
        "households_non_german", "Haushalte nicht deutsch", "Haushalte", 8, "households"
    ),
    *tuple(
        MetricDefinition(
            f"households_size_{key}",
            f"Haushalte mit {label}",
            "Haushaltsgröße",
            7,
            "households",
        )
        for key, label in (
            ("1", "einer Person"),
            ("2", "zwei Personen"),
            ("3", "drei Personen"),
            ("4", "vier Personen"),
            ("5_plus", "fünf oder mehr Personen"),
        )
    ),
    *tuple(
        MetricDefinition(
            f"households_children_{key}",
            f"Haushalte mit {label}",
            "Kinder im Haushalt",
            9,
            "households",
        )
        for key, label in (
            ("1", "einem Kind"),
            ("2", "zwei Kindern"),
            ("3", "drei Kindern"),
            ("4_plus", "vier oder mehr Kindern"),
        )
    ),
)

AGE_KEYS = {
    "0 bis unter 18": "population_age_0_17",
    "18 bis unter 65": "population_age_18_64",
    "65 und älter": "population_age_65_plus",
}
MARITAL_KEYS = {
    "ledig": "population_marital_single",
    "verheiratet": "population_marital_married",
    "geschieden": "population_marital_divorced",
    "verwitwet": "population_marital_widowed",
    "sonstige": "population_marital_other",
    "ohne Angabe": "population_marital_unknown",
}
SUPPRESSED_VALUES = {"", "-", ".", "k.a.", "k.A.", "keine Angabe"}


@dataclass
class StatisticsImportReport:
    status: str
    rows_downloaded: int
    inserted: int
    updated: int
    unchanged: int
    rejected: int
    mapped: int
    unmapped: list[str]
    ambiguous: list[str]
    checksum: str


def parse_value(value: str) -> Decimal | None:
    cleaned = value.strip()
    if cleaned in SUPPRESSED_VALUES:
        return None
    cleaned = cleaned.replace("\u00a0", "").replace(" ", "")
    cleaned = cleaned.removesuffix("%")
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid statistical value: {value!r}") from exc


def _row_metrics(dataset_id: int, row: dict[str, str]) -> list[str]:
    if row.get("Wohnstatus") != "Hauptwohnung":
        return []
    if dataset_id == 6:
        try:
            age_key = AGE_KEYS[row["Altersgruppe"]]
            marital_key = MARITAL_KEYS[row["Familienstand"]]
        except KeyError as exc:
            raise ValueError(
                f"Unknown statistical dimension in dataset {dataset_id}: {exc.args[0]!r}"
            ) from exc
        keys = ["population", age_key, marital_key]
        if row["Migrationshintergrund"] == "Nicht deutsch":
            keys.append("population_non_german")
        return keys
    if dataset_id == 7:
        size = row["ZahlPersonenHaushalt"].replace("+", "_plus")
        return ["households", f"households_size_{size}"]
    if dataset_id == 8:
        return (
            ["households_non_german"]
            if row["Migrationshintergrund_Haushalte"] == "Nicht deutsch"
            else []
        )
    if dataset_id == 9 and row["ZahlKinderHaushalt"]:
        children = row["ZahlKinderHaushalt"].replace("+", "_plus")
        return [f"households_children_{children}"]
    return []


def validate_source_areas(source_names: set[str]) -> tuple[list[str], list[str]]:
    expected_names = {name for name, area_type in AREA_MAPPING.values() if area_type == "DISTRICT"}
    unmapped = sorted(source_names - expected_names)
    missing = sorted(expected_names - source_names)
    if unmapped or missing:
        raise ValueError(f"Area mapping failed: unmapped={unmapped}, missing={missing}")
    return unmapped, missing


def observation_change(current_hash: str | None, new_hash: str) -> str:
    if current_hash is None:
        return "new"
    return "unchanged" if current_hash == new_hash else "updated"


def normalize_rows(
    downloaded: dict[int, list[dict[str, str]]],
) -> tuple[dict[tuple[str, str, int], Decimal | None], set[str]]:
    values: dict[tuple[str, str, int], list[Decimal | None]] = defaultdict(list)
    area_names: set[str] = set()
    metric_columns = {spec.id: spec.metric for spec in DATASET_SPECS}
    for dataset_id, rows in downloaded.items():
        for row in rows:
            area_name = row.get("Stadtteilname", "").strip()
            if not area_name:
                continue
            area_names.add(area_name)
            try:
                year = date.fromisoformat(row["Time"]).year
            except (KeyError, ValueError) as exc:
                raise ValueError(f"Invalid period in dataset {dataset_id}") from exc
            value = parse_value(row[metric_columns[dataset_id]])
            for metric_key in _row_metrics(dataset_id, row):
                values[(metric_key, area_name, year)].append(value)

    aggregated: dict[tuple[str, str, int], Decimal | None] = {}
    for key, parts in values.items():
        aggregated[key] = None if any(part is None for part in parts) else sum(parts, Decimal(0))
    for metric_key, year in {(key[0], key[2]) for key in aggregated}:
        parts = [
            aggregated[(metric_key, name, year)]
            for name, area_type in (value for value in AREA_MAPPING.values())
            if area_type == "DISTRICT" and (metric_key, name, year) in aggregated
        ]
        if len(parts) == 13:
            aggregated[(metric_key, "Flensburg", year)] = (
                None if any(part is None for part in parts) else sum(parts, Decimal(0))
            )
    return aggregated, area_names


async def _ensure_mappings(session: AsyncSession) -> dict[str, ExternalAreaMapping]:
    names = [name for name, _area_type in AREA_MAPPING.values()]
    areas = (await session.scalars(select(AnalysisArea).where(AnalysisArea.name.in_(names)))).all()
    by_key = {(area.name, area.area_type): area for area in areas}
    missing = [
        f"{name} ({area_type})"
        for name, area_type in AREA_MAPPING.values()
        if (name, area_type) not in by_key
    ]
    if missing:
        raise ValueError(
            "Required analysis areas are missing: "
            f"{', '.join(missing)}. Synchronize them first with "
            "`python -m app.cli.sync_analysis_areas --municipality Flensburg` "
            "after loading the OSM boundary data."
        )
    existing = {
        mapping.external_area_id: mapping
        for mapping in (
            await session.scalars(
                select(ExternalAreaMapping).where(ExternalAreaMapping.source == SOURCE)
            )
        ).all()
    }
    for external_id, (name, area_type) in AREA_MAPPING.items():
        area = by_key[(name, area_type)]
        mapping = existing.get(external_id)
        if mapping:
            if mapping.external_area_name != name or mapping.analysis_area_id != area.id:
                raise ValueError(f"Conflicting reviewed mapping for external area {external_id}")
        else:
            mapping = ExternalAreaMapping(
                source=SOURCE,
                external_area_id=external_id,
                external_area_name=name,
                analysis_area_id=area.id,
            )
            session.add(mapping)
            existing[external_id] = mapping
    await session.flush()
    return {mapping.external_area_name: mapping for mapping in existing.values()}


async def _ensure_catalog(
    session: AsyncSession, source_updated_at: datetime
) -> tuple[dict[int, StatisticalDataset], dict[str, StatisticalMetric]]:
    datasets: dict[int, StatisticalDataset] = {}
    for spec in DATASET_SPECS:
        external_id = str(spec.id)
        dataset = await session.scalar(
            select(StatisticalDataset).where(
                StatisticalDataset.source == SOURCE,
                StatisticalDataset.external_dataset_id == external_id,
            )
        )
        if dataset is None:
            dataset = StatisticalDataset(
                source=SOURCE,
                external_dataset_id=external_id,
                name=spec.name,
                source_url=DASHBOARD_URL,
                license=LICENSE,
                update_frequency="annual; checked weekly",
            )
            session.add(dataset)
            await session.flush()
        dataset.name = spec.name
        dataset.source_updated_at = source_updated_at
        datasets[spec.id] = dataset
    metrics: dict[str, StatisticalMetric] = {}
    for definition in METRICS:
        metric = await session.scalar(
            select(StatisticalMetric).where(StatisticalMetric.key == definition.key)
        )
        if metric is None:
            metric = StatisticalMetric(
                dataset_id=datasets[definition.dataset_id].id,
                key=definition.key,
                name=definition.name,
                description=definition.description,
                unit=definition.unit,
                category=definition.category,
                aggregation_method="SUM",
                public=True,
            )
            session.add(metric)
            await session.flush()
        metrics[definition.key] = metric
    return datasets, metrics


def _source_hash(metric_key: str, source_area_id: str, year: int, value: Decimal | None) -> str:
    canonical = json.dumps(
        [metric_key, source_area_id, year, str(value) if value is not None else None],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


async def _mark_import_failed(session: AsyncSession, run_id: int, error: Exception) -> None:
    await session.rollback()
    failed_run = await session.get(StatisticalImportRun, run_id)
    if failed_run:
        failed_run.status = "FAILED"
        failed_run.finished_at = datetime.now(UTC)
        failed_run.error_message = str(error)[:4000]
        await session.commit()


async def import_flensburg_statistics(
    session: AsyncSession,
    client: FlensburgSupersetClient | None = None,
) -> StatisticsImportReport:
    client = client or FlensburgSupersetClient()
    run = StatisticalImportRun(source=SOURCE, status="RUNNING", source_url=DASHBOARD_URL)
    session.add(run)
    await session.commit()
    run_id = run.id
    try:
        mappings = await _ensure_mappings(session)
        dashboard = await client.dashboard()
        charts = await client.charts()
        datasets_inventory = await client.datasets()
        inventory_ids = {int(item["id"]) for item in datasets_inventory}
        expected_ids = {spec.id for spec in DATASET_SPECS}
        if inventory_ids != expected_ids or len(charts) != 27:
            raise ValueError(
                f"Superset inventory drift: datasets={sorted(inventory_ids)}, charts={len(charts)}"
            )
        source_updated_at = datetime.fromisoformat(str(dashboard["changed_on"]))
        if source_updated_at.tzinfo is None:
            source_updated_at = source_updated_at.replace(tzinfo=UTC)
        raw_parts: list[bytes] = []
        downloaded: dict[int, list[dict[str, str]]] = {}
        column_names: dict[int, list[str]] = {}
        for spec in DATASET_SPECS:
            body, rows = await client.download_dataset(spec)
            raw_parts.append(str(spec.id).encode() + b"\0" + body)
            downloaded[spec.id] = rows
            column_names[spec.id] = list(rows[0])
        checksum = hashlib.sha256(b"\0".join(raw_parts)).hexdigest()
        schema_hash = hashlib.sha256(json.dumps(column_names, sort_keys=True).encode()).hexdigest()
        observations, source_names = normalize_rows(downloaded)
        validate_source_areas(source_names)
        datasets, metrics = await _ensure_catalog(session, source_updated_at)
        existing_rows = (await session.scalars(select(StatisticalObservation))).all()
        existing = {
            (row.metric_id, row.analysis_area_id, row.period_start, row.source_area_id): row
            for row in existing_rows
        }
        external_ids = {name: external_id for external_id, (name, _type) in AREA_MAPPING.items()}
        inserted = updated = unchanged = 0
        changed_area_ids: set[object] = set()
        imported_at = datetime.now(UTC)
        for (metric_key, area_name, year), value in observations.items():
            metric = metrics[metric_key]
            mapping = mappings[area_name]
            external_id = external_ids[area_name]
            period_start = date(year, 1, 1)
            row_hash = _source_hash(metric_key, external_id, year, value)
            identity = (metric.id, mapping.analysis_area_id, period_start, external_id)
            current = existing.get(identity)
            change = observation_change(current.source_row_hash if current else None, row_hash)
            if change == "unchanged":
                unchanged += 1
                continue
            statement = insert(StatisticalObservation).values(
                metric_id=metric.id,
                analysis_area_id=mapping.analysis_area_id,
                period_type="YEAR",
                period_start=period_start,
                period_end=date(year, 12, 31),
                value_numeric=value,
                value_text="suppressed" if value is None else None,
                source_area_id=external_id,
                source_row_hash=row_hash,
                is_calculated=area_name == "Flensburg",
                imported_at=imported_at,
                source_updated_at=source_updated_at,
            )
            statement = statement.on_conflict_do_update(
                constraint="uq_statistical_observation",
                set_={
                    "value_numeric": statement.excluded.value_numeric,
                    "value_text": statement.excluded.value_text,
                    "source_row_hash": statement.excluded.source_row_hash,
                    "is_calculated": statement.excluded.is_calculated,
                    "imported_at": statement.excluded.imported_at,
                    "source_updated_at": statement.excluded.source_updated_at,
                },
            )
            await session.execute(statement)
            if change == "updated":
                updated += 1
            else:
                inserted += 1
            changed_area_ids.add(mapping.analysis_area_id)
        for dataset in datasets.values():
            dataset.last_import_at = imported_at
        run = await session.get(StatisticalImportRun, run_id)
        if run is None:
            raise RuntimeError("Import run disappeared")
        run.status = "SUCCESS"
        run.finished_at = imported_at
        run.rows_downloaded = sum(len(rows) for rows in downloaded.values())
        run.rows_imported = inserted
        run.rows_updated = updated
        run.rows_unchanged = unchanged
        run.rows_rejected = 0
        run.checksum = checksum
        run.schema_hash = schema_hash
        run.column_names = json.dumps(column_names, ensure_ascii=False, sort_keys=True)
        session.add(AdminAuditLog(action="FLENSBURG_STATISTICS_SYNC"))
        await enqueue_statistics_summary(session, inserted + updated)
        await bump_cache_versions(session, ("statistics", "analysis-areas"))
        notifications = []
        if changed_area_ids:
            areas = await session.scalars(
                select(AnalysisArea).where(AnalysisArea.id.in_(changed_area_ids))
            )
            for area in areas:
                recipients = await subscription_recipient_ids(
                    session,
                    resource_type="AREA",
                    resource_id=str(area.id),
                    event_type=NotificationEventType.AREA_STATISTICS_UPDATED,
                )
                notifications.extend(
                    await notify_users(
                        session,
                        recipients,
                        DomainEvent(
                            event_type=NotificationEventType.AREA_STATISTICS_UPDATED,
                            resource_type="AREA",
                            resource_id=str(area.id),
                            resource_slug=area.slug,
                            resource_title=area.name,
                        ),
                    )
                )
        await session.commit()
        publish_notifications(notifications)
        return StatisticsImportReport(
            status="SUCCESS",
            rows_downloaded=run.rows_downloaded,
            inserted=inserted,
            updated=updated,
            unchanged=unchanged,
            rejected=0,
            mapped=len(source_names),
            unmapped=[],
            ambiguous=[],
            checksum=checksum,
        )
    except Exception as exc:
        try:
            await _mark_import_failed(session, run_id, exc)
            notifications = await notify_superusers(
                session,
                DomainEvent(
                    event_type=NotificationEventType.IMPORT_FAILED,
                    resource_type="IMPORT",
                    resource_id=str(run_id),
                    resource_title="Flensburg-Statistik",
                ),
            )
            await session.commit()
            publish_notifications(notifications)
        except Exception:
            logger.exception("Could not persist failed Flensburg statistics import run")
        raise
