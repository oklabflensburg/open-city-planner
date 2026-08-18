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

## GIS control semantics

The sidebar uses one control type per interaction model:

- radio buttons select exactly one thematic map presentation;
- switches control binary layer visibility, including Stadtplaner polygons, administrative boundaries and OSM feature layers;
- multi-select toggles include or exclude filter values;
- compact buttons/chips select short values such as sales-area size.

The OpenStreetMap data-source switch is the master for its feature-layer switches. Turning it off disables POIs, area objects and buildings without resetting their individual choices. Turning it on restores the previous child selection. Visibility switches update the existing sources and MapLibre layer visibility; they never recreate the map or replace its style.

## Custom-layer inventory

All application overlays are GeoJSON sources and therefore have no `source-layer`. The VersaTiles basemap is vector-tiled, but none of its source layers is interactive. Imported OSM-derived and manually/local-created sales areas both enter the same `overview-polygons` source; their provenance does not alter interaction or selection.

| Feature type | Source ID / type | Interactive layer | Stable feature ID | Selectable | Universal selection |
| --- | --- | --- | --- | --- | --- |
| Stadtplaner sales area, including OSM-imported and local/manual geometry | `overview-polygons` / PostGIS → GeoJSON | `overview-polygons-fill` | top-level `id`, property `id` | yes | yes |
| Pure OSM business or context polygon | `osm-polygons` / PostGIS → GeoJSON | `osm-polygons-fill` | `promoteId: feature_id` | yes | yes |
| Municipality | `analysis-areas` / PostGIS → GeoJSON | `analysis-areas-municipality-fill` | top-level `id`, property `id` | yes | yes |
| District | `analysis-areas` / PostGIS → GeoJSON | `analysis-areas-district-fill` | top-level `id`, property `id` | yes | yes |
| Quarter | `analysis-areas` / PostGIS → GeoJSON | `analysis-areas-quarter-fill` | top-level `id`, property `id` | yes | yes |
| VersaTiles basemap polygons | configured vector source / MVT | numerous style layers | source-specific | no | no |
| Area boundary and contained polygons on an area detail page | `area-detail-*` / GeoJSON | `area-detail-*` | not required | no, display-only | no |
| Polygon on a sales-area detail page | `detail-polygon` / GeoJSON | `detail-polygon-*` | not required | no, display-only | no |

| Layer ID | Source | Type | Zoom range | Interactive |
| --- | --- | --- | --- | --- |
| `analysis-areas-municipality-fill` | `analysis-areas` | fill | 7–10.5 | yes, fallback |
| `analysis-areas-district-fill` | `analysis-areas` | fill | 9.5–13.5 | yes, fallback |
| `analysis-areas-quarter-fill` | `analysis-areas` | fill | 11.5–24 | yes, fallback |
| `analysis-areas-municipality` | `analysis-areas` | line | 7–10.5 | no |
| `analysis-areas-district` | `analysis-areas` | line | 9.5–13.5 | no |
| `analysis-areas-quarter` | `analysis-areas` | line | 11.5–24 | no |
| `analysis-areas-municipality-label` | `analysis-areas` | symbol | 7.8–10.5 | no |
| `analysis-areas-district-label` | `analysis-areas` | symbol | 10.3–13.5 | no |
| `analysis-areas-quarter-label` | `analysis-areas` | symbol | 12.3–24 | no |
| `osm-polygons-fill` | `osm-polygons` | fill | 14.5+ | yes, OSM polygon |
| `osm-polygons-line` | `osm-polygons` | line | 14.5+ | no |
| `overview-polygons-fill` | `overview-polygons` | fill | all | yes, Stadtplaner polygon |
| `overview-polygons-line` | `overview-polygons` | line | all | no |
| `selected-polygon-fill` | `selected-polygon-source` | fill | all | no, universal selection |
| `selected-polygon-halo` | `selected-polygon-source` | line | all | no, universal selection |
| `selected-polygon-outline` | `selected-polygon-source` | line | all | no, universal selection |
| `osm-clusters` | `osm-pois` | circle | 11+ | yes, cluster |
| `osm-cluster-count` | `osm-pois` | symbol | 11+ | no |
| `osm-poi-circle` | `osm-pois` | circle | 12+ | yes, point POI |
| `osm-selected-point` | `osm-pois` | circle | 11+ | no |
| `osm-poi-label` | `osm-pois` | symbol | 18+ | no |

The central registry in `mapFeaturePicking.ts` is the only list of interactive polygon layers. Picking is deliberately independent of rendered-layer return order. Its priority is point POI, cluster, Stadtplaner polygon, business OSM polygon, quarter, contextual OSM `landuse`/`building`, district, then municipality. This lets a shop win over its containing area while a free part of a quarter remains selectable. Only registered application layers participate; basemap features are excluded.

Every polygon is normalized to `InteractivePolygonFeature` with source, optional vector `sourceLayer`, feature type, geometry type, stable ID and the collision-safe key `source:featureType:id`. Selection itself is source-independent: `selected-polygon-source` contains zero or one Polygon/MultiPolygon with minimal public properties. Its three fixed layers preserve the underlying thematic color, add a white halo and draw the primary outline. POIs remain above this overlay. New selectable polygon sources only require a registry entry and a matching detail target; sources without usable feature-state need no special fallback because the universal overlay is the default path.
