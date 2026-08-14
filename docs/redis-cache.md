# Redis-Read-Cache und GIS-Performance

Redis ist ausschließlich ein temporärer Performance-Layer. PostgreSQL/PostGIS bleibt Source of Truth. Alle Cachezugriffe fallen bei Verbindungsfehlern auf die reguläre Datenbankabfrage zurück.

## Gemessener Ausgangszustand

Gemessen wurde am 14. August 2026 gegen den lokalen Flensburg-Datenbestand. Die Zeiten sind Einzelmessungen und keine SLA.

| Ressource | Uncached Servicezeit | SQL-Abfragen | Features | JSON-Payload |
| --- | ---: | ---: | ---: | ---: |
| OSM Zoom 13 | 168,02 ms | 1 | 2.500 | 892.279 B |
| OSM Zoom 15 | 99,07 ms | 1 | 2.500 | 978.732 B |
| OSM Zoom 17 inkl. Gebäude | 131,66 ms | 1 | 2.496 | 1.198.573 B |
| Analytics Overview | 33,29 ms | 4 | – | 1.264 B |
| Analytics Benchmarks | 3,37 ms | 2 | – | 960 B |
| Analysis-Area-Analytics | 22,65 ms | 5 | – | 1.561 B |
| Analysis-Area-GeoJSON | 7,70 ms | 1 | 51 | 219.405 B |

Der größte kombinierte Engpass war nicht nur PostgreSQL: Die OSM-Antworten liefen in das 2.500er-Limit und erzeugten bis zu 1,2 MB GeoJSON, das anschließend noch von Browser und MapLibre verarbeitet werden musste.

`EXPLAIN ANALYZE` bestätigt für den OSM-Viewport einen Bitmap Index Scan über `idx_osm_features_geometry`. Gebiets-POIs verwenden den GIN-Index `idx_osm_features_tags`; Comparables verwenden `idx_user_polygons_geometry`. Kleine Sequential Scans auf den derzeit rund 42 Stadtplaner-Flächen sind günstiger als ein zusätzlicher Indexzugriff. Der OSM-Lateral-Join zu verknüpften Stadtplaner-Flächen wird erst nach Sortierung und Limit ausgeführt.

## Architektur und Schlüssel

Eine einzige `redis.asyncio.Redis`-Instanz verwaltet den Connection Pool für den FastAPI-Prozess. Startup prüft `PING`, Shutdown schließt den Pool. `REDIS_REQUIRED=false` lässt die Anwendung bei einem Ausfall weiterlaufen.

Alle Schlüssel verwenden kanonisches JSON, sortierte mengenartige Filter und SHA-256:

```text
<CACHE_PREFIX>:v1:<resource>:v<db-version>:<sha256>
```

Beispiele für Ressourcen:

```text
osm:viewport
analytics:fast-facts
analytics:overview
analytics:benchmarks
analysis-area:list
analysis-area:geojson
analysis-area:analytics
analysis-area:comparison
polygons:geojson
polygons:location
polygons:comparables
```

Der OSM-Schlüssel enthält Web-Mercator-Tile-Zoom und X-/Y-Range, gerundeten Darstellungszoom, Kategorien, Gebäudeoption und Limit. Fast identische BBOXen innerhalb derselben Tile-Range teilen damit denselben Cachewert. Die Datenbankabfrage verwendet die normalisierte Tile-Range; die öffentliche API bleibt GeoJSON und es wird keine neue MVT-Infrastruktur eingeführt.

Analytics-Schlüssel enthalten Gebiet, Kategorien, Etagen, Größenklassen, Belegungsstatus, Unternehmensstruktur und den öffentlichen Scope. Private Verwaltungsantworten, Profile und Eigentümerdaten werden nicht shared gecacht.

Die Tabelle `cache_versions` persistiert die Namespaces `osm`, `analytics`, `analysis-areas` und `polygons`. Redis ist damit nicht die einzige Quelle der Invalidierungsversion. Prozesse halten Versionen höchstens fünf Sekunden lokal, um bei Cache-Hits keine PostgreSQL-Abfrage auszulösen.

## TTL und Invalidierung

| Ressource | Standard-TTL |
| --- | ---: |
| OSM-Viewport | 1.800 s |
| Analytics und Fast Facts | 600 s |
| Analysegebiete/GeoJSON | 3.600 s |
| Polygon-GeoJSON | 60 s |
| Standortanalyse/Comparables | 600 s |

Polygon Create, Update, Verwaltung-Update und Delete erhöhen `polygons` und `analytics`. Geometrieänderungen aktualisieren zuvor die räumliche Gebietszuordnung. Kennzahlenänderungen erhöhen `analytics`. Der Boundary-Sync erhöht `analysis-areas` und `analytics`. Ein externer OSM-Import muss anschließend `python -m app.cli.cache_bump osm` aufrufen. OSM-Keys werden bei normalen Polygonänderungen nicht massenhaft gelöscht.

Alte Versionen laufen über ihre TTL beziehungsweise Redis-LRU aus. Pattern-Löschung verwendet `SCAN`, niemals `KEYS *`. Ein kurzer Redis-Lock mit TTL und ein pro Prozess geteilter Async-Lock reduzieren Cache Stampedes; nach kurzer Wartezeit bleibt ein Datenbank-Fallback möglich.

## Nachmessung mit Redis 7

HTTP-Messung über einen separaten lokalen FastAPI-Prozess und Redis 7, inklusive GZip. `X-Cache` war nur für den Benchmark aktiviert.

| Request | MISS | HIT | GZip-Payload | Features |
| --- | ---: | ---: | ---: | ---: |
| OSM Zoom 13 | 405,3 ms | 13,7 ms | 43.944 B | 1.200 |
| OSM Zoom 15 | 217,0 ms | 20,9 ms | 62.630 B | 1.800 |
| OSM Zoom 17 inkl. Gebäude | 284,3 ms | 37,7 ms | 147.012 B | 2.500 |
| Analytics Overview | 71,7 ms | 3,4 ms | 447 B | – |
| Analytics Benchmarks | 16,9 ms | 3,9 ms | 960 B | – |
| Analysis-Area-GeoJSON | 56,1 ms | 15,9 ms | 57.749 B | 51 |

Die reinen OSM-Service-Hits ohne HTTP/GZip lagen nach Speicherung fertiger JSON-Bytes bei 1,7–8,6 ms. Ein minimal verschobener Viewport derselben Tile-Range benötigte 1,7–2,8 ms und keine SQL-Abfrage. Große MISS-Werte enthalten Tile-Bucket-Erweiterung, PostGIS, JSON-Erzeugung und das erstmalige Befüllen von Redis.

## MapLibre und Payload

- Unter Zoom 15 werden höchstens 1.200 Features geliefert.
- Zoom 15 bis unter 17 ist auf 1.800 begrenzt.
- Erst ab Zoom 17 sind maximal 2.500 möglich; mobil bleibt das Limit bei 1.200.
- Gebäude bleiben opt-in und beginnen erst im Detailzoom.
- Punkte werden bis Zoom 14 geclustert.
- Polygone werden abhängig vom Zoom mit `ST_SimplifyPreserveTopology` vereinfacht.
- Requests entstehen auf `moveend`, werden entprellt und über AbortController/Generation abgebrochen.
- Identische Frontend-Request-Keys erzeugen keinen neuen Request; vorhandene Daten bleiben bis zur erfolgreichen Antwort sichtbar.
- MapLibre-Sources bleiben bestehen und werden nur per `setData()` aktualisiert.

## Betrieb und Sicherheit

Beispiel für einen Redis-Server auf derselben Maschine:

```text
bind 127.0.0.1 ::1
protected-mode yes
maxmemory <an den Server-RAM angepasster Wert>
maxmemory-policy allkeys-lru
```

Redis darf nicht öffentlich auf `0.0.0.0:6379` angeboten oder über Nginx weitergereicht werden. Für getrennte Umgebungen sind eindeutige Prefixe wie `stadtplaner:dev`, `stadtplaner:test` und `stadtplaner:prod` erforderlich. Authentifizierung beziehungsweise ACL wird ausschließlich in `REDIS_URL` konfiguriert; Zugangsdaten werden weder geloggt noch dokumentiert.

Da Redis nur Cache ist, darf ein Neustart alle Schlüssel verlieren. AOF/RDB ist fachlich nicht erforderlich. Relevante Diagnosebefehle sind `redis-cli INFO memory`, `redis-cli INFO stats` und `redis-cli DBSIZE`.
