# GIS layer order

Custom MapLibre overlays are registered in `frontend/app/utils/mapLayerOrder.ts`. New overlay layers must be assigned to one of those groups and created through the structural map-infrastructure lifecycle before `ensureStadtplanerLayerOrder()` runs.

The permanent bottom-to-top rule is:

1. analysis areas
2. OSM polygon fills and outlines
3. Stadtplaner polygon fills and outlines
4. polygon selection highlights
5. POI clusters
6. POI points and point selection
7. POI labels

The order is restored after initial map load and every `style.load`. It is not recalculated during `move`, `drag`, or `render`.

## Custom-layer inventory

All sources are GeoJSON sources and therefore have no `source-layer`.

| Layer ID | Source | Type | Zoom range | Interactive |
| --- | --- | --- | --- | --- |
| `analysis-areas-municipality-fill` | `analysis-areas` | fill | 7–10.5 | yes, fallback |
| `analysis-areas-district-fill` | `analysis-areas` | fill | 9.5–13.5 | yes, fallback |
| `analysis-areas-quarter-fill` | `analysis-areas` | fill | 11.5–24 | yes, fallback |
| `analysis-areas-municipality` | `analysis-areas` | line | 7–10.5 | no |
| `analysis-areas-district` | `analysis-areas` | line | 9.5–13.5 | no |
| `analysis-areas-quarter` | `analysis-areas` | line | 11.5–24 | no |
| `analysis-area-selected` | `analysis-areas` | line | all | no |
| `analysis-areas-municipality-label` | `analysis-areas` | symbol | 7.8–10.5 | no |
| `analysis-areas-district-label` | `analysis-areas` | symbol | 10.3–13.5 | no |
| `analysis-areas-quarter-label` | `analysis-areas` | symbol | 12.3–24 | no |
| `osm-polygons-fill` | `osm-polygons` | fill | 14.5+ | yes, OSM polygon |
| `osm-polygons-line` | `osm-polygons` | line | 14.5+ | no |
| `overview-polygons-fill` | `overview-polygons` | fill | all | yes, Stadtplaner polygon |
| `overview-polygons-line` | `overview-polygons` | line | all | no |
| `osm-selected-polygon` | `osm-polygons` | line | 14.5+ | no |
| `osm-clusters` | `osm-pois` | circle | 11+ | yes, cluster |
| `osm-cluster-count` | `osm-pois` | symbol | 11+ | no |
| `osm-poi-circle` | `osm-pois` | circle | 12+ | yes, point POI |
| `osm-selected-point` | `osm-pois` | circle | 11+ | no |
| `osm-poi-label` | `osm-pois` | symbol | 18+ | no |

Picking is deliberately independent of rendered-layer return order. Its priority is point POI, cluster, OSM POI polygon, Stadtplaner polygon, contextual OSM `landuse`/`building` polygon, then analysis area. Only the listed interactive custom layers participate; basemap features are excluded.
