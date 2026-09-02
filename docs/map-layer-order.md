# Reihenfolge der GIS-Layer

Der Slim Host registriert ausschließlich technische Kartenebenen in
`frontend/app/utils/mapLayerOrder.ts`. Die dauerhafte Reihenfolge von unten nach
oben ist:

1. OSM-Polygonfüllungen und -umrisse;
2. generische öffentliche Polygone;
3. die gemeinsame Polygonauswahl;
4. OSM-Cluster und -Punkte;
5. OSM-Beschriftungen;
6. Modul-Overlays aus der `LayerRegistry`.

Die Reihenfolge wird nach dem ersten Kartenladen und nach jedem `style.load`
wiederhergestellt. Während `move`, `drag` oder `render` wird sie nicht neu
berechnet. Modulbeiträge verwenden semantische Gruppen und stabile, vom Modul
besessene IDs; der Host kennt keine fachlichen Layer-IDs.

## Host-Layer

| Layer-ID | Source | Typ | Interaktiv |
| --- | --- | --- | --- |
| `osm-polygons-fill` | `osm-polygons` | fill | ja |
| `osm-polygons-line` | `osm-polygons` | line | nein |
| `overview-polygons-fill` | `overview-polygons` | fill | ja |
| `overview-polygons-line` | `overview-polygons` | line | nein |
| `selected-polygon-fill` | `selected-polygon-source` | fill | nein |
| `selected-polygon-halo` | `selected-polygon-source` | line | nein |
| `selected-polygon-outline` | `selected-polygon-source` | line | nein |
| `osm-clusters` | `osm-pois` | circle | ja |
| `osm-cluster-count` | `osm-pois` | symbol | nein |
| `osm-poi-circle` | `osm-pois` | circle | ja |
| `osm-selected-point` | `osm-pois` | circle | nein |
| `osm-poi-label` | `osm-pois` | symbol | nein |

`mapFeaturePicking.ts` ist die zentrale Registry für Host-eigene interaktive
Layer. Ein Modul registriert Picking, Auswahl und Darstellung über die Map-SDK-
Contributions. `selected-polygon-source` enthält unabhängig von der Herkunft
höchstens ein Polygon oder MultiPolygon. Fachliche Gebiets-, Such-, Vergleichs-
oder Assistant-Overlays existieren nur, wenn das zuständige Modul sie beiträgt.
