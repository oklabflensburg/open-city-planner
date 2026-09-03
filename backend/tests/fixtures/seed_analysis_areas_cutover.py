"""Seed deterministic data for the installed Analysis Areas cutover gate."""

import asyncio

from sqlalchemy import text

from app.db.session import AsyncSessionLocal


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                """
                INSERT INTO analysis_areas (
                  uuid, slug, name, area_type, parent_id, geometry, centroid,
                  area_m2, source, source_osm_type, source_osm_id,
                  source_admin_level, wikidata_id, wikipedia_title,
                  wikidata_match_source, wikidata_match_status,
                  wikidata_match_confidence, wikidata_verified,
                  created_at, updated_at
                ) VALUES (
                  '11111111-1111-4111-8111-111111111111',
                  'flensburg-test', 'Flensburg Test', 'MUNICIPALITY', NULL,
                  ST_Multi(ST_GeomFromText(
                    'POLYGON((9.40 54.76,9.48 54.76,9.48 54.82,9.40 54.82,9.40 54.76))',
                    4326
                  )), ST_SetSRID(ST_Point(9.44, 54.79), 4326),
                  20000000, 'OSM', 'relation', 111, 6, 'Q3798', 'Flensburg',
                  'OSM_WIKIDATA', 'VERIFIED', 1.0, true, now(), now()
                )
                ON CONFLICT (slug) DO NOTHING
                """
            )
        )
        await session.execute(
            text(
                """
                INSERT INTO analysis_areas (
                  uuid, slug, name, area_type, parent_id, geometry, centroid,
                  area_m2, source, source_osm_type, source_osm_id,
                  source_admin_level, wikidata_id, wikipedia_title,
                  wikidata_match_source, wikidata_match_status,
                  wikidata_match_confidence, wikidata_verified,
                  created_at, updated_at
                ) VALUES (
                  '11111111-1111-4111-8111-222222222222',
                  'innenstadt-test', 'Innenstadt Test', 'DISTRICT',
                  (SELECT id FROM analysis_areas WHERE slug = 'flensburg-test'),
                  ST_Multi(ST_GeomFromText(
                    'POLYGON((9.42 54.78,9.45 54.78,9.45 54.80,9.42 54.80,9.42 54.78))',
                    4326
                  )), ST_SetSRID(ST_Point(9.435, 54.79), 4326),
                  3000000, 'OSM', 'relation', 222, 9, 'Q12345', 'Flensburg-Altstadt',
                  'OSM_WIKIDATA', 'VERIFIED', 1.0, true, now(), now()
                )
                ON CONFLICT (slug) DO NOTHING
                """
            )
        )
        await session.execute(
            text(
                """
                INSERT INTO osm_features (osm_type, osm_id, geometry, tags, imported_at)
                VALUES (
                  'node', 197,
                  ST_SetSRID(ST_Point(9.435, 54.79), 4326),
                  '{"amenity":"cafe","name":"Cutover-Café"}'::jsonb,
                  now()
                )
                ON CONFLICT (osm_type, osm_id) DO NOTHING
                """
            )
        )
        await session.execute(
            text(
                """
                INSERT INTO polygon_analysis_areas (
                  polygon_id, analysis_area_id, assignment_type, overlap_ratio, created_at
                )
                SELECT polygon.id, area.id, 'POINT_ON_SURFACE', 1.0, now()
                FROM user_polygons polygon, analysis_areas area
                WHERE polygon.slug = 'e2e-testflaeche'
                  AND area.slug IN ('flensburg-test', 'innenstadt-test')
                ON CONFLICT (polygon_id, analysis_area_id) DO NOTHING
                """
            )
        )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
