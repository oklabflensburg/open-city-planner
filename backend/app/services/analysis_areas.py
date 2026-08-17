import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.analysis_area import AnalysisArea
from app.services.cache_versions import bump_cache_versions
from app.services.social_publishing import enqueue_area_publication


@dataclass
class AnalysisAreaImportReport:
    municipality: str
    municipality_admin_level: int | None = None
    district_admin_level: int | None = None
    quarter_admin_level: int | None = None
    counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    social_events: int = 0


MUNICIPALITY_SQL = text("""
SELECT osm_type, osm_id, tags, imported_at,
       NULLIF(tags->>'admin_level', '')::integer AS admin_level
FROM osm_features
WHERE ST_Dimension(geometry) = 2
  AND tags->>'boundary' = 'administrative'
  AND lower(tags->>'name') = lower(:name)
  AND NULLIF(tags->>'admin_level', '') ~ '^[0-9]+$'
ORDER BY NULLIF(tags->>'admin_level', '')::integer, ST_Area(ST_Transform(geometry, 25832)) DESC
LIMIT 1
""")

LEVELS_SQL = text("""
WITH municipality AS (
  SELECT geometry, NULLIF(tags->>'admin_level', '')::integer AS level
  FROM osm_features WHERE osm_type=:osm_type AND osm_id=:osm_id
)
SELECT NULLIF(feature.tags->>'admin_level', '')::integer AS level, count(*) AS count
FROM osm_features feature CROSS JOIN municipality
WHERE ST_Dimension(feature.geometry)=2
  AND feature.tags->>'boundary'='administrative'
  AND NULLIF(feature.tags->>'admin_level', '') ~ '^[0-9]+$'
  AND NULLIF(feature.tags->>'admin_level', '')::integer > municipality.level
  AND ST_Covers(municipality.geometry, ST_PointOnSurface(feature.geometry))
GROUP BY 1 ORDER BY 1
""")

CANDIDATES_SQL = text("""
WITH municipality AS (
  SELECT geometry FROM osm_features WHERE osm_type=:municipality_type AND osm_id=:municipality_id
), selected AS (
  SELECT feature.osm_type, feature.osm_id, feature.tags, feature.imported_at,
         CASE
           WHEN feature.osm_type=:municipality_type AND feature.osm_id=:municipality_id THEN 'MUNICIPALITY'
           WHEN NULLIF(feature.tags->>'admin_level','')::integer=:district_level THEN 'DISTRICT'
           WHEN NULLIF(feature.tags->>'admin_level','')::integer=:quarter_level THEN 'QUARTER'
         END AS area_type,
         NULLIF(feature.tags->>'admin_level','')::integer AS admin_level,
         ST_IsValid(feature.geometry) AS source_valid,
         ST_Multi(ST_CollectionExtract(ST_MakeValid(feature.geometry), 3)) AS clean_geometry
  FROM osm_features feature CROSS JOIN municipality
  WHERE ST_Dimension(feature.geometry)=2
    AND feature.tags->>'boundary'='administrative'
    AND NULLIF(feature.tags->>'admin_level','') ~ '^[0-9]+$'
    AND ((feature.osm_type=:municipality_type AND feature.osm_id=:municipality_id)
      OR (NULLIF(feature.tags->>'admin_level','')::integer IN (:district_level, :quarter_level)
        AND ST_Covers(municipality.geometry, ST_PointOnSurface(feature.geometry))))
), polygon_places AS (
  SELECT feature.osm_type, feature.osm_id, feature.tags, feature.imported_at,
         CASE WHEN feature.tags->>'place' IN ('borough','suburb') THEN 'DISTRICT' ELSE 'QUARTER' END AS area_type,
         NULL::integer AS admin_level,
         ST_IsValid(feature.geometry) AS source_valid,
         ST_Multi(ST_CollectionExtract(ST_MakeValid(feature.geometry), 3)) AS clean_geometry
  FROM osm_features feature CROSS JOIN municipality
  WHERE ST_Dimension(feature.geometry)=2
    AND feature.tags->>'place' IN ('borough','suburb','quarter','neighbourhood')
    AND ST_Covers(municipality.geometry, ST_PointOnSurface(feature.geometry))
    AND NOT EXISTS (SELECT 1 FROM selected admin WHERE admin.osm_type=feature.osm_type AND admin.osm_id=feature.osm_id)
)
SELECT osm_type, osm_id, tags, imported_at, area_type, admin_level,
       ST_AsEWKB(clean_geometry) AS geometry,
       ST_AsEWKB(ST_PointOnSurface(clean_geometry)) AS centroid,
       ST_Area(ST_Transform(clean_geometry,25832)) AS area_m2,
       source_valid, ST_IsValid(clean_geometry) AS valid
FROM (SELECT * FROM selected UNION ALL SELECT * FROM polygon_places) candidates
WHERE area_type IS NOT NULL AND NOT ST_IsEmpty(clean_geometry)
ORDER BY CASE area_type WHEN 'MUNICIPALITY' THEN 1 WHEN 'DISTRICT' THEN 2 ELSE 3 END, tags->>'name'
""")

UPSERT_SQL = text("""
INSERT INTO analysis_areas
  (uuid, slug, name, area_type, geometry, centroid, area_m2, source, source_osm_type,
   source_osm_id, source_admin_level, source_place, source_osm_wikidata,
   source_osm_wikipedia, source_updated_at, created_at, updated_at)
VALUES
  (:uuid, :slug, :name, :area_type, ST_GeomFromEWKB(:geometry), ST_GeomFromEWKB(:centroid),
   :area_m2, 'OSM', :osm_type, :osm_id, :admin_level, :place, :osm_wikidata,
   :osm_wikipedia, :source_updated_at, now(), now())
ON CONFLICT (source, source_osm_type, source_osm_id) DO UPDATE SET
  name=excluded.name, area_type=excluded.area_type, geometry=excluded.geometry,
  centroid=excluded.centroid, area_m2=excluded.area_m2, source_admin_level=excluded.source_admin_level,
  source_place=excluded.source_place, source_osm_wikidata=excluded.source_osm_wikidata,
  source_osm_wikipedia=excluded.source_osm_wikipedia,
  wikidata_match_status=CASE
    WHEN analysis_areas.wikidata_match_source='MANUAL'
      AND excluded.source_osm_wikidata IS NOT NULL
      AND excluded.source_osm_wikidata IS DISTINCT FROM analysis_areas.wikidata_id THEN 'CONFLICT'
    ELSE analysis_areas.wikidata_match_status END,
  wikidata_last_checked_at=CASE
    WHEN analysis_areas.wikidata_match_source='MANUAL' THEN analysis_areas.wikidata_last_checked_at
    WHEN excluded.source_osm_wikidata IS DISTINCT FROM analysis_areas.source_osm_wikidata
      OR excluded.source_osm_wikipedia IS DISTINCT FROM analysis_areas.source_osm_wikipedia THEN NULL
    ELSE analysis_areas.wikidata_last_checked_at END,
  source_updated_at=excluded.source_updated_at, updated_at=now()
RETURNING id
""")

CURRENT_AREA_SQL = text("""
SELECT id, uuid, name, area_type, area_m2,
       ST_Area(ST_Transform(ST_SymDifference(geometry, ST_GeomFromEWKB(:geometry)),25832)) /
       NULLIF(GREATEST(area_m2, CAST(:area_m2 AS double precision)),0) AS geometry_difference_ratio
FROM analysis_areas
WHERE source='OSM' AND source_osm_type=:osm_type AND source_osm_id=:osm_id
""")

PARENT_SQL = text("""
UPDATE analysis_areas child SET
  parent_id = (
    SELECT candidate.id FROM analysis_areas candidate
    WHERE candidate.id<>child.id
      AND candidate.area_type = CASE child.area_type WHEN 'DISTRICT' THEN 'MUNICIPALITY' WHEN 'QUARTER' THEN 'DISTRICT' END
      AND ST_Covers(candidate.geometry, child.centroid)
    ORDER BY ST_Area(ST_Transform(ST_Intersection(candidate.geometry, child.geometry),25832)) DESC,
             candidate.area_m2 ASC
    LIMIT 1
  ),
  updated_at=now()
WHERE child.source='OSM' AND child.area_type IN ('DISTRICT','QUARTER')
""")


def _slug(value: str, osm_id: int) -> str:
    normalized = value.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-") or "gebiet"
    return f"{normalized}-{osm_id}"


async def refresh_polygon_area_assignments(session: AsyncSession, polygon_id: int | None = None) -> int:
    params = {"polygon_id": polygon_id}
    await session.execute(text("""
      DELETE FROM polygon_analysis_areas
      WHERE (CAST(:polygon_id AS integer) IS NULL OR polygon_id=CAST(:polygon_id AS integer))
    """), params)
    result = await session.execute(text("""
      WITH ranked AS (
        SELECT polygon.id AS polygon_id, area.id AS area_id,
          ST_Area(ST_Transform(ST_Intersection(ST_MakeValid(polygon.geometry), area.geometry),25832)) /
            NULLIF(ST_Area(ST_Transform(ST_MakeValid(polygon.geometry),25832)),0) AS overlap_ratio,
          row_number() OVER (PARTITION BY polygon.id, area.area_type ORDER BY area.area_m2 ASC, area.id) AS rank
        FROM user_polygons polygon JOIN analysis_areas area
          ON ST_Covers(area.geometry, ST_PointOnSurface(ST_MakeValid(polygon.geometry)))
        WHERE (CAST(:polygon_id AS integer) IS NULL OR polygon.id=CAST(:polygon_id AS integer))
      )
      INSERT INTO polygon_analysis_areas (polygon_id, analysis_area_id, assignment_type, overlap_ratio, created_at)
      SELECT polygon_id, area_id, 'POINT_ON_SURFACE', overlap_ratio, now() FROM ranked WHERE rank=1
      RETURNING id
    """), params)
    return len(result.scalars().all())


async def sync_osm_analysis_areas(
    session: AsyncSession,
    municipality_name: str = "Flensburg",
    *,
    publish_relevant_updates: bool = False,
) -> AnalysisAreaImportReport:
    municipality = (await session.execute(MUNICIPALITY_SQL, {"name": municipality_name})).mappings().first()
    if municipality is None:
        raise LookupError(f"Keine administrative OSM-Fläche für {municipality_name!r} gefunden")
    report = AnalysisAreaImportReport(municipality=municipality_name, municipality_admin_level=municipality["admin_level"])
    key = {"osm_type": municipality["osm_type"], "osm_id": municipality["osm_id"]}
    level_rows = (await session.execute(LEVELS_SQL, key)).mappings().all()
    levels = [int(row["level"]) for row in level_rows]
    report.district_admin_level = levels[0] if levels else None
    report.quarter_admin_level = levels[1] if len(levels) > 1 else None
    if report.district_admin_level is None:
        raise LookupError("Keine untergeordnete administrative Flächenebene gefunden")
    if report.quarter_admin_level is None:
        report.warnings.append("Keine zweite untergeordnete administrative Ebene gefunden; polygonale place-Quartiere werden geprüft.")

    params = {
        "municipality_type": municipality["osm_type"], "municipality_id": municipality["osm_id"],
        "district_level": report.district_admin_level, "quarter_level": report.quarter_admin_level or -1,
    }
    rows = (await session.execute(CANDIDATES_SQL, params)).mappings().all()
    counts = {"MUNICIPALITY": 0, "DISTRICT": 0, "QUARTER": 0}
    settings = get_settings()
    for row in rows:
        tags: dict[str, Any] = row["tags"] or {}
        name = str(tags.get("name") or tags.get("name:de") or f"OSM {row['osm_id']}").strip()
        values = {
            "uuid": uuid.uuid4(), "slug": _slug(name, row["osm_id"]), "name": name,
            "area_type": row["area_type"], "geometry": row["geometry"], "centroid": row["centroid"],
            "area_m2": float(row["area_m2"]), "osm_type": row["osm_type"], "osm_id": row["osm_id"],
            "admin_level": row["admin_level"], "place": tags.get("place"), "source_updated_at": row["imported_at"],
            "osm_wikidata": tags.get("wikidata"), "osm_wikipedia": tags.get("wikipedia"),
        }
        previous = (await session.execute(CURRENT_AREA_SQL, values)).mappings().first() if publish_relevant_updates else None
        area_id = (await session.execute(UPSERT_SQL, values)).scalar_one()
        if publish_relevant_updates:
            model = await session.get(AnalysisArea, area_id, populate_existing=True)
            if model is not None:
                if previous is None:
                    queued = await enqueue_area_publication(
                        session, model, "AREA_CREATED", {"name", "geometry", "source"}, settings=settings,
                    )
                else:
                    changed_fields = set()
                    if previous["name"] != name:
                        changed_fields.add("name")
                    if previous["area_type"] != row["area_type"]:
                        changed_fields.add("area_type")
                    boundary_changed = float(previous["geometry_difference_ratio"] or 0) >= settings.mastodon_boundary_change_min_ratio
                    if boundary_changed:
                        changed_fields.update({"geometry", "area_m2"})
                    event_type = "AREA_BOUNDARY_UPDATED" if boundary_changed else "AREA_PUBLIC_DATA_UPDATED"
                    queued = await enqueue_area_publication(session, model, event_type, changed_fields, settings=settings)
                report.social_events += int(queued is not None)
        counts[row["area_type"]] += 1
        if not row["source_valid"]:
            report.warnings.append(f"{name}: ungültige Quellgeometrie wurde beim Import repariert")
        if not row["valid"]:
            report.warnings.append(f"{name}: Geometrie ist nach der Normalisierung weiterhin ungültig")
    report.counts = counts
    await session.execute(PARENT_SQL)
    missing = (await session.execute(text("""
      SELECT name, area_type FROM analysis_areas
      WHERE source='OSM' AND area_type IN ('DISTRICT','QUARTER') AND parent_id IS NULL ORDER BY area_type,name
    """))).all()
    report.warnings.extend(f"{name} ({area_type}): kein räumlich deckender Parent" for name, area_type in missing)
    weak_parents = (await session.execute(text("""
      SELECT child.name, parent.name,
        ST_Area(ST_Transform(ST_Intersection(child.geometry,parent.geometry),25832)) / NULLIF(child.area_m2,0) AS ratio
      FROM analysis_areas child JOIN analysis_areas parent ON parent.id=child.parent_id
      WHERE child.source='OSM' AND
        ST_Area(ST_Transform(ST_Intersection(child.geometry,parent.geometry),25832)) / NULLIF(child.area_m2,0) < 0.95
      ORDER BY child.name
    """))).all()
    report.warnings.extend(
        f"{child}: Parent {parent} deckt nur {ratio:.1%} der Fläche" for child, parent, ratio in weak_parents
    )
    sibling_overlaps = (await session.execute(text("""
      SELECT first.name, second.name,
        ST_Area(ST_Transform(ST_Intersection(first.geometry,second.geometry),25832)) AS overlap_m2
      FROM analysis_areas first JOIN analysis_areas second
        ON first.id<second.id AND first.area_type=second.area_type
       AND first.parent_id IS NOT DISTINCT FROM second.parent_id
      WHERE ST_Area(ST_Transform(ST_Intersection(first.geometry,second.geometry),25832)) > 100
      ORDER BY overlap_m2 DESC
    """))).all()
    report.warnings.extend(
        f"{first}/{second}: Geschwisterflächen überlappen sich um {overlap_m2:.0f} m²"
        for first, second, overlap_m2 in sibling_overlaps
    )
    await refresh_polygon_area_assignments(session)
    await bump_cache_versions(session, ("analysis-areas", "analytics"))
    await session.commit()
    return report
