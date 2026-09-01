# Öffentliche Backend-Service-Ports

Stand dieser Inventarisierung ist `ocp-module-analysis-areas` PR #2, exakt Commit
`a63af188a0cf4ba10a389302bae4c1e0d80cfeda`. Installierte In-Process-Module
dürfen stabile öffentliche Host-Capabilities verwenden. Sie dürfen nie von
privaten Implementierungsdetails einer Host-Fachdomäne abhängen.

Alle Verträge werden ausschließlich aus `app.platform.modules.sdk` importiert
und optional über den unveränderlichen `ModuleContext` injiziert. Konkrete
Implementierungen liegen in `app.integrations.module_host_ports`; dort wird zu
den bestehenden Services komponiert, ohne deren Logik in das SDK zu kopieren.
Die Leseverträge sind seit SDK 1.9 additiv und stabil; die transaktionale
Cache-Generation-Mutation ist seit SDK 1.10 verfügbar. Einen fehlenden optionalen Port
erkennt das konsumierende Modul bei seiner Registrierung. Validierungsfehler bleiben `ValueError`;
ein nicht renderbares Preview wird als `MapPreviewUnavailableError` abstrahiert.
Query-Timeouts werden über `PublicQueryPort.is_timeout()` erkannt, ohne
DB-Treiberfehler zum Modulvertrag zu machen.

## Portübersicht

| Port | Zweck und Owner | Eingabe | Ausgabe / Fehler |
| --- | --- | --- | --- |
| `DatabaseSessionProvider` | Host-eigene Transaktionsgrenze | keine | Async-Kontext mit `AsyncSession`; Exception löst Rollback aus |
| `CachePort` | modulgebundener Byte-Cache | lokaler Key, Bytes, TTL | Bytes/Status; Backend-Ausfall verhält sich als Cache Miss |
| `CacheGenerationPort` | geteilte Read-Model-Invalidierung lesen oder transaktional erhöhen | Session, Ressourcenname beziehungsweise Sequenz | monotone Generation; `bump()` committet nie selbst; keine Redis-/Key-Details |
| `PublicQueryPort` | Host Security | Request, Session, begrenzter Ressourcenname | Guard oder etablierter HTTP-Fehler; `PublicQueryLimits` ist immutable |
| `MapPreviewPort` | Host Map Rendering | `MapPreviewRequest` mit GeoJSON-Primitiven | Bytes, Content-Type, ETag, Cache-Hit; stabile Preview-Exception |
| `PolygonQueryPort` | Polygon-Domäne | Session, immutable `PolygonScope` aus primitiven Polygon-IDs, Limit | immutable `PublicPolygonSummary`; niemals ORM |
| `PolygonAnalyticsPort` | Polygon-/Analytics-Domäne | Session, `PolygonScope`, primitive Filter | `PolygonMetrics` und `CountValue`; niemals SQL-Ausdrücke/ORM |
| `StatisticsQueryPort` | Kommunalstatistik-Domäne | Session, Slug, optionaler Metrik-Key | immutable Statistik-DTOs oder `None` |
| `OsmSnapshotQueryPort` | Plattform-eigener OSM-Snapshot | Session, immutable und begrenzte `OsmSnapshotQuery` | cursor-paginierte, ORM-freie `OsmFeatureSnapshot`-DTOs; Details im [OSM-Vertrag](osm-public-contract.md) |
| `PolygonSpatialMatchPort` | Polygon-Domäne | Session, immutable Area-Geometrien mit EWKB | stabile Polygon-UUIDs und räumliche Match-Metriken; Details im [Polygon-Spatial-Match-Vertrag](polygon-assignment-contract.md) |
| `PolygonIdentityPort` (`platform.polygon-identity@1`) | Polygon-Domäne | Caller-Session, höchstens 5.000 stabile Polygon-UUIDs | immutable UUID↔interne-ID-Zuordnungen und explizite unbekannte UUIDs; niemals ORM |
| `HttpClientFactoryPort` | Plattform-eigener HTTP-Egress | validierter Service-Name, optionale HTTP(S)-Base-URL; danach Methode, Pfad, Header, Parameter und Bytes | begrenzte Response-Projektion oder unveränderte `httpx`-Transport-/Timeout-Exception; keine impliziten Retries |

## Legacy-Import-Inventar und Ownership

Die Klassifikation verwendet A = generische Host-Capability, B = fremde
Fachdomäne, C = Analysis-Areas-owned, D = obsolete Legacy-Kopplung.

| Privater Import / Symbol | Klasse | Öffentlicher Ersatz oder Ziel | Owner |
| --- | --- | --- | --- |
| `app.db.session.get_session` | A | `DatabaseSessionProvider`; das Modul definiert daraus seine FastAPI-Dependency | Platform |
| `app.core.config.get_settings` | A/C | `PublicQueryPort.limits` nur für Host-Limits; Cache-TTLs werden Modulsettings | Platform / Modul |
| `app.cache.service.cache_service` | A | `CachePort` | Platform |
| `app.cache.service.last_cache_status` | C | request-lokaler Status im Modul-Cache-Adapter | Modul |
| `app.cache.keys.build_cache_key` | C | kanonischer Key-Builder im Modul, vor dem bereits Host-seitig namespaceten `CachePort` | Modul |
| `app.services.cache_versions.cache_version` | A | `CacheGenerationPort.current` | Platform |
| `app.services.cache_versions.bump_cache_versions` | A | `CacheGenerationPort.bump`; delegiert an dieselbe Host-Implementierung und Caller-Transaktion | Platform |
| `app.services.public_query_security.guard_public_query` | A | `PublicQueryPort.guard` | Platform Security |
| `app.services.public_query_security.is_statement_timeout_error` | A | `PublicQueryPort.is_timeout` | Platform Security |
| `app.services.map_previews.map_preview_service` | A | `MapPreviewPort.render` | Map Preview |
| `app.services.map_previews.MapPreviewError` | A | `MapPreviewUnavailableError` | Map Preview |
| `app.models.user_polygon.UserPolygon` | B | `PolygonQueryPort` / `PolygonAnalyticsPort` und DTOs | Polygons |
| direkte UUID→ID-Abfrage auf `app.models.user_polygon.UserPolygon` | B | `PolygonIdentityPort` über `platform.polygon-identity@1` | Polygons |
| `app.services.analytics._base_filters` | B | primitive `PolygonFilterValues` am `PolygonAnalyticsPort` | Polygon Analytics |
| `app.services.analytics._benchmark_metrics` | B | `PolygonAnalyticsPort.metrics` | Polygon Analytics |
| `app.services.analytics._counts` | B | `PolygonAnalyticsPort.category_counts` | Polygon Analytics |
| `app.services.area_statistics.area_statistics` | B | `StatisticsQueryPort.for_area` | Statistics |
| `app.services.area_statistics.area_statistic_series` | B | `StatisticsQueryPort.series_for_area` | Statistics |
| `app.services.poi_categories.AREA_POI_CATEGORY_SQL` | C | kleine OSM-Tag-Projektion zusammen mit der bestehenden Gebiet-POI-Query im Modul | Modul |
| `app.services.social_publishing.enqueue_area_publication` | D | Der unregistrierte externe Legacy-Sync entfällt; kein spekulativer Social-Port | Social Publishing |
| `app.schemas.analytics.BenchmarkMetrics` | B | `PolygonMetrics`, danach module-owned API-Schema | Polygon Analytics / Modul |
| `app.schemas.analytics.IndustryCount` | B | `CountValue`, danach module-owned API-Schema | Polygon Analytics / Modul |
| `app.schemas.statistics.AreaStatisticsRead` | B | `AreaStatistics`, danach module-owned Response-Schema | Statistics / Modul |
| `app.schemas.statistics.AreaStatisticSeriesRead` | B | `AreaStatisticSeries`, danach module-owned Response-Schema | Statistics / Modul |
| `app.schemas.geojson.AreaGeometry` | C | module-owned GeoJSON-Pydantic-Typ | Modul |
| `app.schemas.external_links.ExternalLinks` | C | module-owned Response-Typ | Modul |
| `app.schemas.external_links.WikidataExternalLink` | C | module-owned Response-Typ | Modul |
| `app.schemas.external_links.WikipediaExternalLink` | C | module-owned Response-Typ | Modul |
| `app.schemas.polygon_filters.PolygonFilterParams` | C | module-owned HTTP-Parsing; Übergabe als `PolygonFilterValues` | Modul |
| `app.schemas.polygon_filters.polygon_filter_query` | C | module-owned FastAPI-Dependency | Modul |

`AREA_POI_CATEGORY_SQL`, API-Schemas, Filter-Parsing, Cache-Key-Building,
Social-Publishing und Response-Mapping werden bewusst nicht als Host-Port
veröffentlicht: Sie bestimmen
die konkrete Analysis-Areas-Antwort. Die privaten Analytics-Helfer bleiben privat;
nur der bestehende Host-Adapter darf sie hinter fachlich benannten Operationen
aufrufen. Der direkte Sessionimport ist ersatzlos obsolet, weil SDK 1.2 bereits
die passende Transaktionsgrenze besitzt.

## Area→Polygon-Ownership und Consumer-Flow

Das Area-owning Modul verwaltet Gebietszustand, -geometrie und seine konkrete
Polygon↔Gebiet-Relation. Die Polygon-Domäne verwaltet `user_polygons` und stellt mit
dem `PolygonSpatialMatchPort` ausschließlich eine generische räumliche Leseoperation
bereit. Ein Modul übergibt opaque Area-Referenzen und Geometrien, erhält stabile
Polygon-UUIDs sowie Match-Metriken zurück und löst benötigte Relationsschlüssel über
`platform.polygon-identity@1` auf. Der begrenzte Resolver dedupliziert Eingaben
stabil, liefert aufgelöste Werte in eindeutiger Eingabereihenfolge und führt
unbekannte UUIDs explizit unter `missing`. Er verwendet genau eine mengenbasierte
Abfrage gegen Host-owned `user_polygons` und übernimmt weder Commit noch Rollback.
Das Modul gleicht seine eigene Relation anschließend in seiner eigenen Transaktion
ab; der Host liest oder schreibt diese fremde Relation nie.

Für Polygon-Lese- und Analytics-Flows bleibt `PolygonScope` der neutrale Scope.
`UserPolygon` und räumliche Berechnung bleiben Host-intern; domänenspezifische
Assignment-Persistenz bleibt Consumer-intern.

## Lifecycle und Datenschutz

Die Adapter werden einmal beim Host-Composition-Root erzeugt und pro
`ModuleContext` injiziert. Das gilt für die Web-Runtime und den Outbox-Worker, da
beide aktive Module beziehungsweise deren Jobs ausführen. Der Cache wird zusätzlich
an die Modul-ID gebunden und seine Keys mit dem konfigurierten Deployment-Prefix
versehen.

Jeder über `HttpClientFactoryPort.create()` erzeugte HTTP-Client ist an seinen
Async-Context-Manager gebunden. Der Host besitzt Timeout, Pool-Limits, festen
User-Agent, Redirect-Policy und bestehende externe Request-Observability. Der
Adapter injiziert oder übernimmt keine Host-Credentials, Cookies, internen Tokens
oder Proxy-Credentials. Der validierte Service-Name und die HTTP-Methode sind
stabile Observability-Dimensionen; URL und Queryparameter sind keine Labels.
Retries bleiben Consumer-/Job-Policy und werden nicht im Adapter dupliziert.

Die übrigen Ports nehmen weder Secrets noch Benutzerobjekte entgegen.
Polygonprojektionen enthalten nur bereits öffentliche Felder. Keine Exception
enthält Query-Text, Parameter oder Treiberantworten.

## Settings-Auflösung

Der externe Adapter liest am gepinnten Stand genau
`public_polygon_response_limit`, `cache_debug_headers`,
`analysis_area_cache_ttl`, `analytics_cache_ttl` und
`mastodon_boundary_change_min_ratio`. Die ersten beiden Werte liefert der
immutable `PublicQueryLimits`-Contract. Die beiden Cache-TTLs sind Policy der
module-owned Read-Modelle und werden im Folgecommit als kleine namespacete
Moduleinstellungen mit den bisherigen Defaults geführt. Der Mastodon-Schwellwert
wird ausschließlich vom nicht registrierten `legacy_sync.py` gelesen; dieser Pfad
entfällt extern und erhält daher keinen öffentlichen Settings- oder Social-Port.

Host-interne Cachewerte (`cache_prefix`, Payload-Warnschwelle und Lock-TTL) und
sämtliche Preview-/Rate-Limit-/Statement-Timeout-Konfiguration bleiben vollständig
hinter ihren Adaptern. Weder `Settings` noch Redis-, Renderer- oder DB-Treiber-Typen
werden über die Modulgrenze gereicht.
