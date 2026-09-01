"""Polygon-owned spatial assignment mutation for caller-managed transactions."""

import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.modules.sdk import PolygonAssignmentRequest, PolygonAssignmentResult

_INVALID_AREAS_SQL = text("""
WITH supplied AS (
  SELECT external_id::uuid AS external_id,
         ST_GeomFromEWKB(decode(geometry_hex, 'hex')) AS geometry
  FROM jsonb_to_recordset(CAST(:areas AS jsonb))
    AS item(external_id text, geometry_hex text)
)
SELECT supplied.external_id::text
FROM supplied
LEFT JOIN analysis_areas area ON area.uuid = supplied.external_id
WHERE area.id IS NULL
   OR ST_SRID(supplied.geometry) <> 4326
   OR ST_Dimension(supplied.geometry) <> 2
   OR ST_IsEmpty(supplied.geometry)
ORDER BY supplied.external_id
""")


_REFRESH_ASSIGNMENTS_SQL = text("""
WITH supplied AS (
  SELECT external_id::uuid AS external_id, selection_group,
         ST_GeomFromEWKB(decode(geometry_hex, 'hex')) AS geometry
  FROM jsonb_to_recordset(CAST(:areas AS jsonb))
    AS item(external_id text, selection_group text, geometry_hex text)
), candidates AS (
  SELECT polygon.id AS polygon_id, area.id AS area_id,
         ST_Area(ST_Transform(ST_Intersection(
           ST_MakeValid(polygon.geometry), supplied.geometry
         ), 25832)) /
         NULLIF(ST_Area(ST_Transform(ST_MakeValid(polygon.geometry), 25832)), 0)
           AS overlap_ratio,
         row_number() OVER (
           PARTITION BY polygon.id, supplied.selection_group
           ORDER BY ST_Area(ST_Transform(supplied.geometry, 25832)) ASC,
                    supplied.external_id
         ) AS rank
  FROM user_polygons polygon
  CROSS JOIN supplied
  JOIN analysis_areas area ON area.uuid = supplied.external_id
  WHERE ST_SRID(supplied.geometry) = 4326
    AND ST_Covers(
      supplied.geometry,
      ST_PointOnSurface(ST_MakeValid(polygon.geometry))
    )
), desired AS (
  SELECT polygon_id, area_id, overlap_ratio FROM candidates WHERE rank = 1
), removed AS (
  DELETE FROM polygon_analysis_areas assignment
  WHERE NOT EXISTS (
    SELECT 1 FROM desired
    WHERE desired.polygon_id = assignment.polygon_id
      AND desired.area_id = assignment.analysis_area_id
  )
  RETURNING assignment.id
), updated AS (
  UPDATE polygon_analysis_areas assignment
  SET overlap_ratio = desired.overlap_ratio,
      assignment_type = 'POINT_ON_SURFACE'
  FROM desired
  WHERE assignment.polygon_id = desired.polygon_id
    AND assignment.analysis_area_id = desired.area_id
    AND (assignment.overlap_ratio IS DISTINCT FROM desired.overlap_ratio
         OR assignment.assignment_type IS DISTINCT FROM 'POINT_ON_SURFACE')
  RETURNING assignment.id
), created AS (
  INSERT INTO polygon_analysis_areas
    (polygon_id, analysis_area_id, assignment_type, overlap_ratio, created_at)
  SELECT desired.polygon_id, desired.area_id, 'POINT_ON_SURFACE',
         desired.overlap_ratio, now()
  FROM desired
  WHERE NOT EXISTS (
    SELECT 1 FROM polygon_analysis_areas assignment
    WHERE assignment.polygon_id = desired.polygon_id
      AND assignment.analysis_area_id = desired.area_id
  )
  ON CONFLICT (polygon_id, analysis_area_id) DO NOTHING
  RETURNING id
)
SELECT
  (SELECT count(*) FROM user_polygons) AS processed_polygons,
  (SELECT count(*) FROM created) AS created_assignments,
  (SELECT count(*) FROM updated) AS updated_assignments,
  (SELECT count(*) FROM removed) AS removed_assignments,
  (SELECT count(*) FROM desired)
    - (SELECT count(*) FROM created)
    - (SELECT count(*) FROM updated) AS unchanged_assignments
""")


def _serialized_areas(request: PolygonAssignmentRequest) -> str:
    return json.dumps(
        [
            {
                "external_id": area.external_id,
                "selection_group": area.selection_group,
                "geometry_hex": area.geometry_wkb.hex(),
            }
            for area in request.areas
        ],
        separators=(",", ":"),
    )


async def refresh_polygon_assignments(
    session: AsyncSession, request: PolygonAssignmentRequest
) -> PolygonAssignmentResult:
    """Reconcile the complete snapshot without committing the caller's session."""

    serialized = _serialized_areas(request)
    invalid = tuple(
        (await session.execute(_INVALID_AREAS_SQL, {"areas": serialized})).scalars()
    )
    if invalid:
        raise ValueError(
            "Unknown or invalid polygon assignment areas: " + ", ".join(invalid)
        )
    row = (
        await session.execute(_REFRESH_ASSIGNMENTS_SQL, {"areas": serialized})
    ).mappings().one()
    return PolygonAssignmentResult(
        processed_polygons=int(row["processed_polygons"]),
        created_assignments=int(row["created_assignments"]),
        updated_assignments=int(row["updated_assignments"]),
        removed_assignments=int(row["removed_assignments"]),
        unchanged_assignments=int(row["unchanged_assignments"]),
    )


__all__ = ["refresh_polygon_assignments"]
