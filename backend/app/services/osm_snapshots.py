"""Bounded, stable OSM read projections for the public module contract."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.modules.sdk import (
    OsmFeatureCursor,
    OsmFeatureSnapshot,
    OsmFeatureSnapshotPage,
    OsmSnapshotQuery,
)


async def list_osm_feature_snapshots(
    session: AsyncSession, query: OsmSnapshotQuery
) -> OsmFeatureSnapshotPage:
    conditions = ["NOT ST_IsEmpty(geometry)", "ST_Dimension(geometry) IN (0, 2)"]
    parameters: dict[str, object] = {"row_limit": query.limit + 1}
    if query.osm_types:
        conditions.append("osm_type = ANY(CAST(:osm_types AS text[]))")
        parameters["osm_types"] = list(query.osm_types)
    if query.geometry_kinds:
        dimensions = [0 if kind == "point" else 2 for kind in query.geometry_kinds]
        conditions.append("ST_Dimension(geometry) = ANY(CAST(:dimensions AS integer[]))")
        parameters["dimensions"] = dimensions
    if query.required_tag_keys:
        conditions.append("tags ?& CAST(:required_tag_keys AS text[])")
        parameters["required_tag_keys"] = list(query.required_tag_keys)
    for index, tag_filter in enumerate(query.tag_filters):
        key_parameter = f"tag_key_{index}"
        conditions.append(f"tags ? :{key_parameter}")
        parameters[key_parameter] = tag_filter.key
        if tag_filter.values:
            values_parameter = f"tag_values_{index}"
            conditions.append(
                f"tags ->> :{key_parameter} = ANY(CAST(:{values_parameter} AS text[]))"
            )
            parameters[values_parameter] = list(tag_filter.values)
    if query.bbox is not None:
        conditions.append(
            "geometry && ST_MakeEnvelope(:west, :south, :east, :north, 4326)"
        )
        parameters.update(
            dict(zip(("west", "south", "east", "north"), query.bbox, strict=True))
        )
    if query.cursor is not None:
        conditions.append("(osm_type, osm_id) > (:cursor_type, :cursor_id)")
        parameters.update(
            cursor_type=query.cursor.osm_type,
            cursor_id=query.cursor.osm_id,
        )
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = (
        await session.execute(
            text(f"""
SELECT osm_type, osm_id, tags, ST_AsEWKB(geometry) AS geometry_wkb,
       ST_XMin(Box2D(geometry)) AS west, ST_YMin(Box2D(geometry)) AS south,
       ST_XMax(Box2D(geometry)) AS east, ST_YMax(Box2D(geometry)) AS north,
       imported_at
FROM osm_features
{where}
ORDER BY osm_type, osm_id
LIMIT :row_limit
"""),
            parameters,
        )
    ).mappings().all()
    has_more = len(rows) > query.limit
    rows = rows[: query.limit]
    items = tuple(
        OsmFeatureSnapshot(
            osm_type=row["osm_type"],
            osm_id=row["osm_id"],
            tags=row["tags"],
            geometry_wkb=bytes(row["geometry_wkb"]),
            bbox=(row["west"], row["south"], row["east"], row["north"]),
            imported_at=row["imported_at"],
        )
        for row in rows
    )
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = OsmFeatureCursor(last.osm_type, last.osm_id)
    return OsmFeatureSnapshotPage(items=items, next_cursor=next_cursor)


__all__ = ["list_osm_feature_snapshots"]
