# Reihenfolge der GIS-Layer

Eigene MapLibre-Overlays sind in `frontend/app/utils/mapLayerOrder.ts` registriert. Neue Layer müssen einer dort definierten Gruppe zugeordnet und im strukturellen Kartenlebenszyklus erzeugt werden, bevor `ensureStadtplanerLayerOrder()` läuft.

Die dauerhafte Reihenfolge von unten nach oben lautet:

1. Analysegebiete;
2. Füllungen und Umrisse von OSM-Polygonen;
3. Füllungen und Umrisse von Stadtplaner-Polygonen;
4. Hervorhebung der Polygonauswahl;
5. POI-Cluster;
6. POI-Punkte und Punktauswahl;
7. POI-Beschriftungen.

Die Reihenfolge wird nach dem ersten Kartenladen und nach jedem `style.load` wiederhergestellt. Während `move`, `drag` oder `render` wird sie nicht neu berechnet.

## Semantik der GIS-Bedienelemente

Die Sidebar verwendet pro Interaktionsmodell genau einen Bedienelementtyp:

- Radiobuttons wählen genau eine thematische Kartendarstellung;
- Schalter steuern die binäre Sichtbarkeit von Stadtplaner-Polygonen, Gebietsgrenzen und OSM-Layern;
- Mehrfachauswahlen schließen Filterwerte ein oder aus;
- kompakte Schaltflächen beziehungsweise Chips wählen kurze Werte wie die Verkaufsflächengröße.

Der OpenStreetMap-Datenquellenschalter ist der Hauptschalter seiner Feature-Layer. Beim Ausschalten werden POIs, Flächenobjekte und Gebäude deaktiviert, ohne ihre Einzelauswahl zurückzusetzen. Beim erneuten Einschalten wird die vorherige Auswahl wiederhergestellt. Sichtbarkeitsschalter aktualisieren vorhandene Sources und MapLibre-Layer; sie erzeugen weder die Karte noch ihren Stil neu.

## Inventar der Anwendungslayer

Alle Anwendungs-Overlays sind GeoJSON-Sources und besitzen deshalb kein `source-layer`. Die VersaTiles-Basiskarte verwendet Vektorkacheln, ihre Layer sind jedoch nicht interaktiv. Aus OSM übernommene und lokal beziehungsweise manuell erzeugte Stadtplaner-Flächen liegen gemeinsam in `overview-polygons`; ihre Herkunft ändert Auswahl und Interaktion nicht.

| Objekttyp | Source / Typ | Interaktiver Layer | Stabile Feature-ID | Auswählbar | Allgemeine Auswahl |
| --- | --- | --- | --- | --- | --- |
| Stadtplaner-Fläche einschließlich OSM-Übernahme | `overview-polygons` / PostGIS → GeoJSON | `overview-polygons-fill` | oberste `id` und Property `id` | ja | ja |
| Reines OSM-Geschäfts- oder Kontextpolygon | `osm-polygons` / PostGIS → GeoJSON | `osm-polygons-fill` | `promoteId: feature_id` | ja | ja |
| Gemeinde | `analysis-areas` / PostGIS → GeoJSON | `analysis-areas-municipality-fill` | oberste `id` und Property `id` | ja | ja |
| Stadtteil | `analysis-areas` / PostGIS → GeoJSON | `analysis-areas-district-fill` | oberste `id` und Property `id` | ja | ja |
| Quartier | `analysis-areas` / PostGIS → GeoJSON | `analysis-areas-quarter-fill` | oberste `id` und Property `id` | ja | ja |
| VersaTiles-Basiskartenpolygone | konfigurierte Vector Source / MVT | mehrere Style-Layer | sourceabhängig | nein | nein |
| Gebietsgrenze und enthaltene Polygone auf Gebietsdetailseiten | `area-detail-*` / GeoJSON | `area-detail-*` | nicht erforderlich | nein, reine Anzeige | nein |
| Polygon auf einer Flächendetailseite | `detail-polygon` / GeoJSON | `detail-polygon-*` | nicht erforderlich | nein, reine Anzeige | nein |

| Layer-ID | Source | Typ | Zoombereich | Interaktiv |
| --- | --- | --- | --- | --- |
| `analysis-areas-municipality-fill` | `analysis-areas` | fill | 7–10,5 | ja, Fallback |
| `analysis-areas-district-fill` | `analysis-areas` | fill | 9,5–13,5 | ja, Fallback |
| `analysis-areas-quarter-fill` | `analysis-areas` | fill | 11,5–24 | ja, Fallback |
| `analysis-areas-municipality` | `analysis-areas` | line | 7–10,5 | nein |
| `analysis-areas-district` | `analysis-areas` | line | 9,5–13,5 | nein |
| `analysis-areas-quarter` | `analysis-areas` | line | 11,5–24 | nein |
| `analysis-areas-municipality-label` | `analysis-areas` | symbol | 7,8–10,5 | nein |
| `analysis-areas-district-label` | `analysis-areas` | symbol | 10,3–13,5 | nein |
| `analysis-areas-quarter-label` | `analysis-areas` | symbol | 12,3–24 | nein |
| `osm-polygons-fill` | `osm-polygons` | fill | ab 14,5 | ja, OSM-Polygon |
| `osm-polygons-line` | `osm-polygons` | line | ab 14,5 | nein |
| `overview-polygons-fill` | `overview-polygons` | fill | alle | ja, Stadtplaner-Polygon |
| `overview-polygons-line` | `overview-polygons` | line | alle | nein |
| `selected-polygon-fill` | `selected-polygon-source` | fill | alle | nein, allgemeine Auswahl |
| `selected-polygon-halo` | `selected-polygon-source` | line | alle | nein, allgemeine Auswahl |
| `selected-polygon-outline` | `selected-polygon-source` | line | alle | nein, allgemeine Auswahl |
| `osm-clusters` | `osm-pois` | circle | ab 11 | ja, Cluster |
| `osm-cluster-count` | `osm-pois` | symbol | ab 11 | nein |
| `osm-poi-circle` | `osm-pois` | circle | ab 12 | ja, POI-Punkt |
| `osm-selected-point` | `osm-pois` | circle | ab 11 | nein |
| `osm-poi-label` | `osm-pois` | symbol | ab 18 | nein |

Die zentrale Registry in `mapFeaturePicking.ts` ist die einzige Liste interaktiver Polygonlayer. Die Auswahl ist bewusst unabhängig von der Rückgabereihenfolge gerenderter Layer. Die Priorität lautet: POI-Punkt, Cluster, Stadtplaner-Polygon, OSM-Geschäftspolygon, Quartier, kontextuelles OSM-`landuse` oder `building`, Stadtteil und Gemeinde. Dadurch gewinnt ein Geschäft gegenüber seinem umschließenden Gebiet, während ein freier Teil eines Quartiers auswählbar bleibt. Basiskartenobjekte sind ausgeschlossen.

Jedes Polygon wird zu `InteractivePolygonFeature` mit Source, optionalem Vector-`sourceLayer`, Featuretyp, Geometrietyp, stabiler ID und dem kollisionssicheren Schlüssel `source:featureType:id` normalisiert. `selected-polygon-source` enthält unabhängig von der Herkunft höchstens ein Polygon oder MultiPolygon mit minimalen öffentlichen Properties. Drei feste Layer erhalten die Themenfarbe, ergänzen einen weißen Halo und zeichnen den primären Umriss. POIs bleiben darüber sichtbar. Eine neue auswählbare Polygonquelle benötigt nur einen Registry-Eintrag und ein passendes Detailziel.
