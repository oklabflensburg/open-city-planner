# Lokale OpenStreetMap-Daten

Stadtplaner fragt OpenStreetMap-Informationen beim Auswählen einer Fläche bedarfsgesteuert ab. Die primäre Quelle ist die lokale PostGIS-Tabelle `osm_features`. Es werden keine OSM-Tags in `user_polygons` kopiert und die Oberfläche verändert keine OSM-Daten.

## Bestand und Importvertrag

Vor Einführung dieser Schnittstelle enthielten Datenbank und Repository keinen OSM-Import und keine Tabellen wie `planet_osm_*`, `osm_points`, `ways`, `nodes` oder `relations`. Die Migration `20260813_0009` führt deshalb einen kleinen, importerunabhängigen Vertrag ein:

| Spalte | Inhalt |
| --- | --- |
| `osm_type` | `node`, `way` oder `relation` |
| `osm_id` | numerische OSM-ID; zusammen mit `osm_type` Primärschlüssel |
| `geometry` | Point- oder Flächengeometrie in EPSG:4326 |
| `tags` | OSM-Tags als JSONB |
| `imported_at` | Zeitpunkt des Imports |

`idx_osm_features_geometry` ist ein GiST-Index für räumliche Abfragen. `idx_osm_features_tags` ist ein GIN-Index. Ein Importjob darf diese Tabelle per Upsert aktualisieren, zum Beispiel mit `ON CONFLICT (osm_type, osm_id) DO UPDATE`. Für die Anwendung ist sie fachlich read-only. Linien werden derzeit nicht als Flächentreffer ausgewertet.

Ein bestehender osm2pgsql-/Imposm-Prozess kann seine relevanten POIs und Gebäude in diesen Vertrag projizieren. Die Anwendung selbst lädt oder seedet keine erfundenen OSM-Daten.

## Lookup

Der Lookup verwendet zunächst `geometry && polygon.geometry`, damit PostgreSQL den GiST-Index benutzt. Punkte werden mit `ST_Within` zugeordnet. Flächen benötigen `ST_Intersects` sowie eine Intersection mit positiver Fläche. Der Überdeckungswert ist die Schnittfläche geteilt durch die OSM-Objektfläche; Flächenberechnungen erfolgen nach `ST_Transform(..., 25832)`. `ST_MakeValid` verhindert Fehler durch ungültige Importgeometrien.

Treffer werden nach vollständiger Überdeckung, Überdeckungswert, fachlich spezifischem Tag und vorhandenem Namen sortiert. Die API liefert höchstens `OSM_LOOKUP_MAX_MATCHES` Objekte und keine Geometrien.

## Optionaler Overpass-Fallback

Der Fallback ist standardmäßig aus und wird ausschließlich serverseitig aktiv, wenn beide Werte gesetzt sind:

```dotenv
OSM_EXTERNAL_FALLBACK_ENABLED=true
OVERPASS_API_URL=https://bewusst-ausgewählter-endpoint.example/api/interpreter
```

Die URL ist nicht hartcodiert. `OVERPASS_TIMEOUT_SECONDS`, `OSM_EXTERNAL_MIN_INTERVAL_SECONDS` und `OSM_LOOKUP_CACHE_TTL_SECONDS` steuern Timeout, Prozess-Rate-Limit und Cache. Der Cache-Schlüssel enthält Polygon-ID und `updated_at`; eine Geometrieänderung erzeugt damit automatisch einen neuen Eintrag. Lokale Treffer verhindern jeden externen Request.
