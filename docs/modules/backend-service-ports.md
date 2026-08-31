# Öffentliche Backend-Service-Ports

Stand dieser Inventarisierung ist der Merge von `ocp-module-analysis-areas` PR #2,
exakt Commit `06afb05fed5dab8426e0e52392d3716ba46c980a`. Installierte In-Process-Module
dürfen stabile öffentliche Host-Capabilities verwenden. Sie dürfen nie von
privaten Implementierungsdetails einer Host-Fachdomäne abhängen.

Alle Verträge werden ausschließlich aus `app.platform.modules.sdk` importiert
und optional über den unveränderlichen `ModuleContext` injiziert. Konkrete
Implementierungen liegen in `app.integrations.module_host_ports`; dort wird zu
den bestehenden Services komponiert, ohne deren Logik in das SDK zu kopieren.
Die Verträge sind seit SDK 1.9 additiv und stabil. Einen fehlenden optionalen Port
erkennt das konsumierende Modul bei seiner Registrierung. Validierungsfehler bleiben `ValueError`;
ein nicht renderbares Preview wird als `MapPreviewUnavailableError` abstrahiert.
Query-Timeouts werden über `PublicQueryPort.is_timeout()` erkannt, ohne
DB-Treiberfehler zum Modulvertrag zu machen.

## Portübersicht

| Port | Zweck und Owner | Eingabe | Ausgabe / Fehler |
| --- | --- | --- | --- |
| `DatabaseSessionProvider` | Host-eigene Transaktionsgrenze | keine | Async-Kontext mit `AsyncSession`; Exception löst Rollback aus |
| `CachePort` | modulgebundener Byte-Cache | lokaler Key, Bytes, TTL | Bytes/Status; Backend-Ausfall verhält sich als Cache Miss |
| `CacheGenerationPort` | geteilte Read-Model-Invalidierung lesen | Session, Ressourcenname | monotone Generation; keine Redis-/Key-Details |
| `PublicQueryPort` | Host Security | Request, Session, begrenzter Ressourcenname | Guard oder etablierter HTTP-Fehler; `PublicQueryLimits` ist immutable |
| `MapPreviewPort` | Host Map Rendering | `MapPreviewRequest` mit GeoJSON-Primitiven | Bytes, Content-Type, ETag, Cache-Hit; stabile Preview-Exception |
| `PolygonQueryPort` | Polygon-Domäne | Session, immutable `PolygonScope` aus primitiven Polygon-IDs, Limit | immutable `PublicPolygonSummary`; niemals ORM |
| `PolygonAnalyticsPort` | Polygon-/Analytics-Domäne | Session, `PolygonScope`, primitive Filter | `PolygonMetrics` und `CountValue`; niemals SQL-Ausdrücke/ORM |
| `StatisticsQueryPort` | Kommunalstatistik-Domäne | Session, Slug, optionaler Metrik-Key | immutable Statistik-DTOs oder `None` |

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
| `app.services.cache_versions.bump_cache_versions` | D | Der unregistrierte externe Legacy-Sync entfällt; kein mutierender Cache-Port | Modul / Platform |
| `app.services.public_query_security.guard_public_query` | A | `PublicQueryPort.guard` | Platform Security |
| `app.services.public_query_security.is_statement_timeout_error` | A | `PublicQueryPort.is_timeout` | Platform Security |
| `app.services.map_previews.map_preview_service` | A | `MapPreviewPort.render` | Map Preview |
| `app.services.map_previews.MapPreviewError` | A | `MapPreviewUnavailableError` | Map Preview |
| `app.models.user_polygon.UserPolygon` | B | `PolygonQueryPort` / `PolygonAnalyticsPort` und DTOs | Polygons |
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
Cache-Bumping, Social-Publishing und Response-Mapping werden bewusst nicht als
Host-Port veröffentlicht: Sie bestimmen
die konkrete Analysis-Areas-Antwort. Die privaten Analytics-Helfer bleiben privat;
nur der bestehende Host-Adapter darf sie hinter fachlich benannten Operationen
aufrufen. Der direkte Sessionimport ist ersatzlos obsolet, weil SDK 1.2 bereits
die passende Transaktionsgrenze besitzt.

## Area→Polygon-Ownership und Consumer-Flow

Der erste Entwurf nahm eine Gebiet-UUID entgegen und löste sie im Host über die
Built-in-Modelle `AnalysisArea` und `PolygonAnalysisArea` auf. Das war ein
Ownership Leak: Nach dem Cutover soll dieses Built-in-Package entfernt werden,
und die Relation gehört fachlich zum externen Modul.

Das externe Modul löst künftig innerhalb einer vom vorhandenen
`DatabaseSessionProvider` gelieferten Session zunächst seine eigene
`AnalysisArea` auf. Danach liest es aus seinem eigenen
`PolygonAnalysisArea`-Modell die primitiven Integer-IDs und erzeugt einen
unveränderlichen `PolygonScope`. Nur dieser neutrale Scope wird an
`PolygonQueryPort.list_by_scope`, `PolygonAnalyticsPort.metrics` oder
`PolygonAnalyticsPort.category_counts` übergeben. Ein nicht vorhandenes Gebiet
behandelt das Modul vor dem Port-Aufruf selbst.

Der Host kennt dadurch weder Gebiet-UUID noch Relationstabelle. `UserPolygon` und
die Analytics-Implementierung bleiben vollständig intern. Für größere Scopes
bindet der Host alle IDs als einen PostgreSQL-Arrayparameter mit `ANY`; er erzeugt
keine expandierte `IN (...)`-Parameterliste. Die Relation wird in genau einer
module-owned Query gelesen, das Aggregat anschließend in genau einer Host-Query
berechnet.

## Lifecycle und Datenschutz

Die Adapter werden einmal beim Host-Composition-Root erzeugt und pro
`ModuleContext` injiziert. Der Cache wird zusätzlich an die Modul-ID gebunden und
seine Keys mit dem konfigurierten Deployment-Prefix versehen. Die Ports nehmen
weder Secrets noch Benutzerobjekte entgegen. Polygonprojektionen enthalten nur
bereits öffentliche Felder. Keine Exception enthält Query-Text, Parameter oder
Treiberantworten.

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
