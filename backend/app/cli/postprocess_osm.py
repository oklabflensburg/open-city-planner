import argparse
import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic

from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.observability.jobs import observed_job
from app.observability.metrics import OSM_REPLICATION_LAG
from app.services.cache_versions import bump_cache_versions

REGION_SQL = """
SELECT geometry
FROM osm_import.osm_features_stage
WHERE osm_type='R'
  AND tags->>'boundary'='administrative'
  AND tags->>'ISO3166-2'='DE-SH'
LIMIT 1
"""

UPSERT_SQL = text(f"""
WITH region AS ({REGION_SQL}), selected AS (
  SELECT CASE stage.osm_type WHEN 'N' THEN 'node' WHEN 'W' THEN 'way' ELSE 'relation' END AS osm_type,
         stage.osm_id, stage.geometry, stage.tags
  FROM osm_import.osm_features_stage stage CROSS JOIN region
  WHERE ST_Dimension(stage.geometry) IN (0, 2)
    AND ST_Intersects(stage.geometry, region.geometry)
), changed AS (
  INSERT INTO osm_features (osm_type, osm_id, geometry, tags, imported_at)
  SELECT osm_type, osm_id, geometry, tags, now() FROM selected
  ON CONFLICT (osm_type, osm_id) DO UPDATE SET
    geometry=excluded.geometry, tags=excluded.tags, imported_at=now()
  WHERE osm_features.geometry IS DISTINCT FROM excluded.geometry
     OR osm_features.tags IS DISTINCT FROM excluded.tags
  RETURNING (xmax = 0) AS inserted
)
SELECT count(*) FILTER (WHERE inserted) AS inserted,
       count(*) FILTER (WHERE NOT inserted) AS updated
FROM changed
""")

DELETE_SQL = text(f"""
WITH region AS ({REGION_SQL})
DELETE FROM osm_features feature
USING region
WHERE NOT EXISTS (
  SELECT 1
  FROM osm_import.osm_features_stage stage
  WHERE stage.osm_type = CASE feature.osm_type
    WHEN 'node' THEN 'N'
    WHEN 'way' THEN 'W'
    WHEN 'relation' THEN 'R'
  END
    AND stage.osm_id = feature.osm_id
    AND ST_Dimension(stage.geometry) IN (0, 2)
    AND stage.geometry && region.geometry
    AND ST_Intersects(stage.geometry, region.geometry)
  OFFSET 0
)
""")

STATE_SQL = text("""
INSERT INTO osm_sync_state
  (singleton, sequence, osm_timestamp, last_success_at, inserted_count, updated_count, deleted_count)
VALUES (true, :sequence, :osm_timestamp, now(), :inserted, :updated, :deleted)
ON CONFLICT (singleton) DO UPDATE SET
  sequence=excluded.sequence,
  osm_timestamp=excluded.osm_timestamp,
  last_success_at=excluded.last_success_at,
  inserted_count=excluded.inserted_count,
  updated_count=excluded.updated_count,
  deleted_count=excluded.deleted_count
""")

REFRESH_POLYGON_OSM_SOURCES_SQL = text("""
UPDATE polygon_osm_sources source SET
  osm_snapshot=feature.tags,
  source_geometry=feature.geometry,
  source_updated_at=feature.imported_at
FROM osm_features feature
WHERE source.osm_type=feature.osm_type AND source.osm_id=feature.osm_id
  AND (source.osm_snapshot IS DISTINCT FROM feature.tags
    OR source.source_geometry IS DISTINCT FROM feature.geometry)
""")


@dataclass(frozen=True)
class ReconciliationCounts:
    inserted: int
    updated: int
    deleted: int


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def progress(enabled: bool, started_at: float, phase: str, **values: object) -> None:
    if not enabled:
        return
    details = " ".join(f"{key}={value}" for key, value in values.items())
    suffix = f" {details}" if details else ""
    print(
        f"OSM_POSTPROCESS_PROGRESS phase={phase} elapsed_seconds={monotonic() - started_at:.1f}{suffix}",
        flush=True,
    )


@observed_job("osm_replication")
async def run(
    sequence: int | None,
    osm_timestamp: datetime,
    *,
    verbose: bool = False,
) -> None:
    started_at = monotonic()
    OSM_REPLICATION_LAG.set(max(0.0, (datetime.now(UTC) - osm_timestamp).total_seconds()))
    progress(verbose, started_at, "start", sequence=sequence, timestamp=osm_timestamp.isoformat())
    async with AsyncSessionLocal() as session:
        progress(verbose, started_at, "validate_region")
        if await session.scalar(text(f"SELECT EXISTS ({REGION_SQL})")) is not True:
            raise SystemExit("DE-SH boundary relation is missing from osm_import.osm_features_stage")

        progress(verbose, started_at, "upsert_features")
        upserted = (await session.execute(UPSERT_SQL)).mappings().one()
        progress(
            verbose,
            started_at,
            "upsert_features_done",
            inserted=int(upserted["inserted"] or 0),
            updated=int(upserted["updated"] or 0),
        )
        progress(verbose, started_at, "delete_missing_features")
        deleted = (await session.execute(DELETE_SQL)).rowcount or 0
        counts = ReconciliationCounts(
            inserted=int(upserted["inserted"] or 0),
            updated=int(upserted["updated"] or 0),
            deleted=int(deleted),
        )
        progress(verbose, started_at, "delete_missing_features_done", deleted=counts.deleted)

        progress(verbose, started_at, "refresh_polygon_osm_sources")
        refreshed_sources = (await session.execute(REFRESH_POLYGON_OSM_SOURCES_SQL)).rowcount or 0
        progress(verbose, started_at, "refresh_polygon_osm_sources_done", sources=refreshed_sources)
        progress(verbose, started_at, "update_cache_and_state")
        await bump_cache_versions(session, ("osm", "analytics", "polygons"))
        await session.execute(
            STATE_SQL,
            {
                "sequence": sequence,
                "osm_timestamp": osm_timestamp,
                "inserted": counts.inserted,
                "updated": counts.updated,
                "deleted": counts.deleted,
            },
        )
        progress(verbose, started_at, "commit")
        await session.commit()
        progress(verbose, started_at, "commit_done")

    print(
        f"OSM_POSTPROCESS sequence={sequence if sequence is not None else 'initial'} "
        f"timestamp={osm_timestamp.isoformat()} inserted={counts.inserted} "
        f"updated={counts.updated} deleted={counts.deleted}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="osm2pgsql staging data atomically publish")
    parser.add_argument("--sequence", type=int)
    parser.add_argument("--timestamp", required=True, type=parse_timestamp)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.sequence, args.timestamp, verbose=args.verbose))
