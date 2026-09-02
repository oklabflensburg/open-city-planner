# Redis-Read-Cache

Redis ist ausschließlich ein optionaler technischer Performance-Layer.
PostgreSQL/PostGIS bleibt Source of Truth. Cachezugriffe fallen bei
Verbindungsfehlern auf die reguläre Datenbankabfrage zurück, sofern Redis nicht
für den produktiven Sicherheitsbetrieb als erforderlich konfiguriert ist.

Eine Prozess-weite `redis.asyncio.Redis`-Instanz verwaltet den Connection Pool.
Startup prüft `PING`, Shutdown schließt den Pool. Schlüssel verwenden kanonisches
JSON und SHA-256:

```text
<CACHE_PREFIX>:v1:<resource>:v<db-version>:<sha256>
```

Der Slim Host besitzt Cachegenerationen für `osm` und `polygons`. OSM-
Postprocessing erhöht beide Generationen; Polygonmutationen erhöhen `polygons`.
Installierte Module erhalten über `CachePort` einen eigenen
`module:<module-id>:`-Namespace und können über `CacheGenerationPort` ihre
Read-Modelle explizit versionieren. Der Host kennt keine fachlichen
Analysis-Areas-, Search-, Assistant-, Comparison-, Statistics- oder Social-
Fallback-Keys.

OSM-Viewport-Schlüssel enthalten den normalisierten Kartenausschnitt,
Darstellungszoom und neutrale Filter. Polygon-GeoJSON verwendet die öffentliche
Scope-/Limit-Projektion. Private Verwaltungsantworten, Profile und
Eigentümerdaten werden nicht gemeinsam gecacht.

Alte Versionen laufen über TTL beziehungsweise Redis-LRU aus. Pattern-Löschung
verwendet `SCAN`, niemals `KEYS *`. Kurze verteilte und prozesslokale Locks
reduzieren Cache Stampedes; nach kurzer Wartezeit bleibt ein Datenbank-Fallback
möglich.
