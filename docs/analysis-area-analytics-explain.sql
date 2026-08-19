\if :{?area_id}
\else
\echo 'Bitte mit -v area_id=<interne numerische Gebiets-ID> aufrufen.'
\quit
\endif

-- Bisherige Abfrage als Vergleichsbasis. Auf großen Datenbeständen kann sie
-- innerhalb des konfigurierten statement_timeout abgebrochen werden.
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT
  coalesce(
    tags->>'shop',
    tags->>'amenity',
    tags->>'tourism',
    tags->>'leisure',
    'other'
  ) AS category,
  count(*) AS count
FROM osm_features
WHERE ST_Covers(
    (SELECT geometry FROM analysis_areas WHERE id = :area_id),
    ST_PointOnSurface(geometry)
  )
  AND (
    tags ? 'shop'
    OR tags ? 'amenity'
    OR tags ? 'tourism'
    OR tags ? 'leisure'
  )
GROUP BY 1
ORDER BY count(*) DESC, 1;

-- Optimierte Abfrage mit indexierbarer räumlicher Vorauswahl.
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
WITH target AS (
  SELECT geometry
  FROM analysis_areas
  WHERE id = :area_id
)
SELECT
  coalesce(
    osm.tags->>'shop',
    osm.tags->>'amenity',
    osm.tags->>'tourism',
    osm.tags->>'leisure',
    'other'
  ) AS category,
  count(*) AS count
FROM osm_features osm
CROSS JOIN target
WHERE osm.geometry && target.geometry
  AND ST_Covers(target.geometry, ST_PointOnSurface(osm.geometry))
  AND (
    osm.tags ? 'shop'
    OR osm.tags ? 'amenity'
    OR osm.tags ? 'tourism'
    OR osm.tags ? 'leisure'
  )
GROUP BY 1
ORDER BY count(*) DESC, 1;

-- Kandidatenzahl vor der exakten ST_Covers-Prüfung separat sichtbar machen.
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
WITH target AS (
  SELECT geometry
  FROM analysis_areas
  WHERE id = :area_id
)
SELECT count(*) AS bbox_candidates
FROM osm_features osm
CROSS JOIN target
WHERE osm.geometry && target.geometry
  AND (
    osm.tags ? 'shop'
    OR osm.tags ? 'amenity'
    OR osm.tags ? 'tourism'
    OR osm.tags ? 'leisure'
  );
