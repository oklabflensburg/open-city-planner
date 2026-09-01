"""Read-only spatial matching against Host-owned user polygons."""

import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.modules.sdk import (
    PolygonSpatialMatch,
    PolygonSpatialMatchRequest,
    PolygonSpatialMatchResult,
)

_INVALID_GEOMETRIES_SQL = text("""
WITH supplied AS (
  SELECT external_id,
         ST_GeomFromEWKB(decode(geometry_hex, 'hex')) AS geometry
  FROM jsonb_to_recordset(CAST(:areas AS jsonb))
    AS item(external_id text, geometry_hex text)
)
SELECT external_id
FROM supplied
WHERE ST_SRID(geometry) <> 4326
   OR ST_Dimension(geometry) <> 2
   OR ST_IsEmpty(geometry)
ORDER BY external_id
""")

_MATCH_POLYGONS_SQL = text("""
WITH supplied AS (
  SELECT external_id, selection_group,
         ST_GeomFromEWKB(decode(geometry_hex, 'hex')) AS geometry
  FROM jsonb_to_recordset(CAST(:areas AS jsonb))
    AS item(external_id text, selection_group text, geometry_hex text)
), ranked AS (
  SELECT polygon.uuid::text AS polygon_id,
         supplied.external_id AS external_area_id,
         supplied.selection_group,
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
  WHERE ST_Covers(
    supplied.geometry,
    ST_PointOnSurface(ST_MakeValid(polygon.geometry))
  )
)
SELECT polygon_id, external_area_id, selection_group, overlap_ratio
FROM ranked
WHERE rank = 1
ORDER BY polygon_id, selection_group, external_area_id
""")


def _serialized_areas(request: PolygonSpatialMatchRequest) -> str:
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


async def match_user_polygons(
    session: AsyncSession, request: PolygonSpatialMatchRequest
) -> PolygonSpatialMatchResult:
    """Return stable spatial matches without mutating or committing the session."""

    serialized = _serialized_areas(request)
    invalid = tuple(
        (await session.execute(_INVALID_GEOMETRIES_SQL, {"areas": serialized})).scalars()
    )
    if invalid:
        raise ValueError("Invalid polygon spatial areas: " + ", ".join(invalid))
    rows = (
        await session.execute(_MATCH_POLYGONS_SQL, {"areas": serialized})
    ).mappings()
    return PolygonSpatialMatchResult(
        matches=tuple(
            PolygonSpatialMatch(
                polygon_id=row["polygon_id"],
                external_area_id=row["external_area_id"],
                selection_group=row["selection_group"],
                overlap_ratio=(
                    float(row["overlap_ratio"])
                    if row["overlap_ratio"] is not None
                    else None
                ),
            )
            for row in rows
        )
    )


__all__ = ["match_user_polygons"]
