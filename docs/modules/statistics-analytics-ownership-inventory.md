# Statistics und Analytics: Ownership- und Extraktionsinventar

Stand: 2026-09-04 · Issue
[#128](https://github.com/oklabflensburg/open-city-planner/issues/128) · Basis
`staging/epic-91-modular-host` bei `07219391b5eefa3b9f6587ee77bff20335783b8c`

## Ergebnis

Der im Issue beschriebene Ausgangszustand existiert auf dem aktuellen Staging-Stand
nicht mehr vollständig. Die Slim-Host-Extraktion aus PR #212 hat die aktive
Statistics-/Analytics-Runtime bereits aus dem Host entfernt. Insbesondere fehlen
heute `app/api/analytics.py`, `app/services/analytics.py`,
`app/services/area_statistics.py`, Statistics-Import und -Superset-Client sowie die
früheren Analytics-/Vergleichsseiten und Stores. Die Boundary-Tests verhindern ihre
unbeabsichtigte Wiedereinführung.

Das veröffentlichte Modul `statistics` 0.2.0 ist bereits der einzige aktive Owner
der lesenden kommunalen Statistiklogik. Das Modul `analysis-areas` 1.5.3 besitzt
Gebietshierarchie, gebietsbezogene Analytics-/Comparison-Orchestrierung, deren APIs
und die vollständige Gebietsdetailseite einschließlich Statistikdarstellung. Ein
zusätzliches generisches `analytics`-Modul würde diese fachlich kohärente Grenze
derzeit künstlich auftrennen.

Im Host verbleiben drei unterschiedliche Dinge:

1. öffentliche, fachneutral transportierbare SDK-Verträge;
2. polygon-eigene Aggregation über die Host-Tabelle `user_polygons`, bis die
   Polygon-Domäne in #129 externalisiert wird;
3. die inaktive `city_metrics`-Tabelle ohne Runtime-ORM sowie unveränderliche
   historische Statistics-Migrationen.

## Audit-Methode und Klassifikation

Der geforderte repositoryweite Suchlauf wurde auf Backend, Frontend,
Dokumentation und Scripts ausgeführt. Die Begriffe ergaben 731 Zeilentreffer. Die
Matrix klassifiziert sie semantisch nach Pfadgruppen; reine Worttreffer wie
Prometheus-Metriken, Performance-Messwerte oder redaktionelle Vergleiche sind keine
Statistics-/Analytics-Domänenlogik.

| Aktueller Pfad / Treffergruppe | Klassifikation | Owner und Begründung |
| --- | --- | --- |
| `backend/app/platform/modules/sdk.py`: `Statistics*`, `Statistic*`, `StatisticsQueryPort`, Service-ID/-Version | `CROSS_MODULE_CONTRACT` | Host-SDK. Immutable DTOs und Protocol bleiben die öffentliche Grenze; keine Persistence oder Fachorchestrierung. |
| `backend/app/platform/modules/sdk.py`: `PolygonScope`, `PolygonFilterValues`, `PolygonMetrics`, `PolygonAnalyticsPort` | `CROSS_MODULE_CONTRACT` | Öffentliche Polygon-Capability. Der Name beschreibt das Ergebnis, nicht eine eigenständige Analytics-Domäne. |
| `backend/app/integrations/module_host_ports.py`: `HostPolygonAnalytics` und Hilfsfilter | `OTHER_DOMAIN_CONSUMER` | Adapter der noch host-owned Polygon-Domäne. Greift ausschließlich auf `UserPolygon` zu und zieht keine Statistics-/Analysis-Areas-Persistence in den Host. Übergabe an #129. |
| `backend/app/services/polygon_analytics.py`, `schemas/polygon_analytics.py` | `OTHER_DOMAIN_CONSUMER` | Polygon-eigene Aggregate und private Abbildungsschemas. Zusammen mit Polygon-Persistence in #129 externalisieren, nicht in ein Statistics-Modul verschieben. |
| `backend/app/api/polygons.py`, `services/polygons.py`, `schemas/geojson.py` (`/{polygon_id}/metrics`) | `OTHER_DOMAIN_CONSUMER` | Geometrische Kennzahlen einer einzelnen Fläche sind Bestandteil des öffentlichen Polygon-Vertrags. |
| `backend/app/main.py`, `platform/modules/context.py` mit Polygon-Port-Injektion | `CROSS_MODULE_CONTRACT` | Fachneutrale Composition Root. Keine Modul-ID-Sonderlogik und keine kopierte Aggregation. |
| ehemalige `backend/app/models/city_metrics.py`, Export in `models/__init__.py` und explizites Anonymisieren in `services/account_service.py` | `LEGACY` | In #219 aus Runtime und Metadata entfernt. Kein Router, Service, Job oder UI liest/schreibt die Tabelle; PostgreSQL erzwingt die Anonymisierung über `ON DELETE SET NULL`. |
| `20260813_0008_add_city_metrics.py` | `LEGACY` | Veröffentlichte, unveränderliche Migration; die Tabelle bleibt bis zu einer gesonderten Datenhaltungsentscheidung erhalten. |
| `20260816_0016_flensburg_statistics.py`, `20260901_0035_decouple_statistics_areas.py` | `LEGACY` | Historische Production-Lineage. `0016` erzeugt Statistics-Tabellen, berührt aber auch Host-`cache_versions`; `0035` liest beim Upgrade und rekonstruiert beim Downgrade `analysis_areas`. Deshalb derzeit keine sichere exklusive Modul-Adoption. |
| `20260813_0007_add_polygon_analytics_indexes.py` | `OTHER_DOMAIN_CONSUMER` | Historische Polygon-Migration; keine Statistics-Persistence. |
| `20260814_0015_cache_versions.py` sowie Cache-/Generationstreffer | `HOST_PRIMITIVE` | Generische Cache-Infrastruktur. Namespace-Strings begründen keine Domain-Ownership. |
| Referenzmodul-Merge-Revision und `tests/fixtures/service_modules/statistics/**` | `TEST_FIXTURE` | Prüfen globalen Migrationsgraph beziehungsweise Service Registry, implementieren keine Produktivdomäne. |
| `backend/tests/test_module_{sdk,host_ports,service_registry,persistence}.py`, `test_external_module_imports.py` | `TEST_FIXTURE` | Positive Contract-, Adapter- und Architecture-Tests. |
| `backend/tests/test_slim_host_boundaries.py` | `TEST_FIXTURE` | Negativer Guard gegen entfernte Statistics-/Analytics-Legacypfade. |
| `backend/tests/fixtures/{assert,seed}_analysis_areas_cutover.py`, `test_analysis_areas_migration_regression.py` | `TEST_FIXTURE` | End-to-End-Regressionsicherung für installierte Module und erhaltene Statistics-Daten. |
| `frontend/app/components/analysis/PolygonStatistics.vue`, `PolygonMetricCard.vue`, Polygon-Store/API/Typen und `/flaechen/[slug]` | `OTHER_DOMAIN_CONSUMER` | Darstellung polygon-eigener Geometrie-/Statusdaten. Sie gehört mit dem Polygon-Frontend zu #129. |
| Frontend-Tests zu Polygon-Metriken, Auswahl und Layout | `TEST_FIXTURE` | Charakterisieren den aktuellen Polygon-Vertrag; keine kommunale Statistik. |
| `frontend/e2e-cutover/analysis-areas-cutover.spec.ts` | `TEST_FIXTURE` | Prüft die extern beigetragene Gebietsdetailseite samt Statistics Summary/Series. |
| entfernte Hostpfade in Backend-/Frontend-Slim-Host-Guards | `LEGACY` | Nur Negativlisten historischer Pfade, keine Runtime. |
| Observability `MetricsPort`, `/metrics`, Prometheus/Grafana, Job-/HTTP-Metriken und zugehörige Tests/Deploy-Dateien | `HOST_PRIMITIVE` | Technische Telemetrie; ausdrücklich nicht fachliche Analytics. |
| OSM-Postprocessing-Zähler, Notification-Texte/-Events, Projektkatalog, Performance-Script und andere fachfremde `metric`-/`Statistik`-/`Vergleich`-Worttreffer | `OTHER_DOMAIN_CONSUMER` | Eigenständige Domänen oder redaktionelle Inhalte; kein Import der Statistics-/Analytics-Persistence. |
| `docs/**`, Backend-/Frontend-README und frühere Inventare mit diesen Begriffen | `DOCUMENTATION` | Architektur-, Betriebs- oder historische Beschreibung. |

Es gibt im aktuellen Host keine Datei der Klassifikation `STATISTICS_DOMAIN` oder
`ANALYTICS_DOMAIN` mehr, die aktive Runtime-Funktionalität dieser Domänen
implementiert. Die einzigen fachlichen Hostreste sind als `LEGACY` ausgewiesen.

## Externes Statistics-Modul 0.2.0

Geprüft wurde der annotierte Tag `v0.2.0` im Repository
`oklabflensburg/ocp-module-statistics`; er löst auf Commit
`4525491995cddb7ad9670f456bba1a49e289f583` auf.

| Bestandteil | Bereits extern vorhanden | Noch nicht vorhanden |
| --- | --- | --- |
| Manifest / Lifecycle | Capability `statistics.query`, SDK `>=1.15.0,<2.0.0`; keine Modulabhängigkeit | keine Settings, Permissions oder Jobs |
| Service-Vertrag | Provider für `statistics.query@1` / `StatisticsQueryPort` | kein Write-/Import-Port |
| Queries | Summary und Series, nur öffentliche Metriken, Quellenmetadaten, Gemeinde-Vergleich, Decimal-/Date-DTOs | kein Katalog-/Status-/Administrations-API |
| Persistence | Read-Ownership für die fünf bestehenden unqualifizierten Tabellen als `adopted_tables` | keine eigene Migrationsquelle; kein Schema-Move oder Daten-Copy |
| Sicherheit | parametrisierte SQL-Statements, kein privater Hostimport, Aufrufer besitzt Session/Transaktion | Importvalidierung und Providerfehler sind mangels Import noch nicht abgedeckt |
| Frontend | leeres, buildbares Nuxt-Layer | keine eigenständige Seite, Navigation, Charts oder Verwaltung |

Die fünf eindeutig Statistics-owned Tabellen sind
`statistical_datasets`, `statistical_metrics`, `external_area_mappings`,
`statistical_observations` und `statistical_import_runs`. Version 0.2.0 deklariert
sie als bestehende Tabellen im Schema `public`; es existiert keine zweite
Tabellenstruktur.

## Analytics-Entscheidung

Für #128 wird **kein separates Analytics-Modul** eingeführt.

- Kommunale Beobachtungen, Zeitreihen, Metrikdefinitionen, Quellen und Imports sind
  Statistics-owned.
- Gebietsauswahl, Quartier-Vererbung, Gebiet-vs.-Gemeinde-Vergleich,
  POI-Auswertung und die Komposition von Statistics-, Polygon- und OSM-Daten sind
  Analysis-Areas-owned. Version 1.5.3 implementiert diese Application-Logik, APIs,
  Cache-Policy, DTOs und Visualisierung bereits ohne fremde ORM-Imports.
- Aggregate über `user_polygons` sind Polygon-owned. Der öffentliche
  `PolygonAnalyticsPort` verhindert, dass Analysis Areas das Polygon-ORM importiert.
  Provider und private Schemas wechseln deshalb später gemeinsam mit #129.
- Historische globale Fast Facts aus `city_metrics` haben keine aktive Funktion
  mehr. Für eine tote Tabelle wird kein Modul geschaffen. Eine spätere
  Wiedereinführung stadtweiter Benchmarks benötigt zuerst ein eigenes Produkt- und
  Datenquellen-Issue und darf dann als Statistics-Capability oder klar begründetes
  Modul entworfen werden.
- Die frühere `/vergleich`-Seite und `/api/v1/analytics/**` sind seit der
  Slim-Host-Extraktion ausdrücklich kein aktueller Hostvertrag. Sie werden in #128
  nicht stillschweigend mit unbekannter Semantik rekonstruiert. Der noch vorhandene
  Link der Gebietsdetailseite auf `/vergleich` ist eine bekannte Einschränkung des
  Analysis-Areas-Moduls, aber kein Grund für einen privaten Cross-Module-Import.

## Aktuelle öffentliche Verträge

Der aktuelle produktive Statistics-Zugriff verläuft über die von
`analysis-areas` 1.5.3 beigetragenen Routen:

- `GET /api/v1/analysis-areas/by-slug/{slug}/statistics`
- `GET /api/v1/analysis-areas/by-slug/{slug}/statistics/{metric_key}`

Analysis Areas löst UUID/String-Darstellung, Hierarchie und Vererbung auf, ruft
`statistics.query@1` auf und übersetzt die SDK-DTOs in seine Response-Schemas. Die
Gebietsdetailseite lädt Summary und, falls vorhanden, die Population-Series
SSR-fähig. Ihre gebietsbezogenen Analytics- und Comparison-Routen bleiben ebenfalls
Analysis-Areas-owned. Es gibt aktuell keine öffentliche Statistics-Route direkt am
Statistics-Modul und keine `/api/v1/analytics`-Route im Host.

## Dependency Graph

```text
Host-Plattform
  ├─ SDK / Service Registry / DB-Session / Migration Coordinator
  │    └─ statistics 0.2.0
  │         └─ statistics.query@1
  │              └─ analysis-areas 1.5.3
  ├─ Polygon Query + PolygonAnalyticsPort ───────────┘
  ├─ OSM Snapshot / Cache / Public Query / Map Ports ┘
  └─ historische Host-Alembic-Lineage 0016 → … → 0035

analysis-areas 1.5.3
  ├─ eigene Gebietspersistenz und Hierarchie
  ├─ gebietsbezogene Analytics-/Comparison-Orchestrierung
  ├─ Statistics-/Analytics-HTTP-Adapter
  └─ Gebietsseiten, Statistikdarstellung und Visualisierungen
```

Manifestseitig gilt `analysis-areas -> statistics >=0.2.0,<1.0.0`. Statistics darf
keine Rückabhängigkeit auf Analysis Areas einführen. Ein künftiger Statistics-Import
ordnet externe Gebiete über die Statistics-owned Mappingtabelle zu; falls dafür
Gebietsidentitäten benötigt werden, ist ausschließlich ein öffentlicher Lookup-Port
zulässig.

## Persistence- und Migrationsgrenze

Runtime-Tabellenownership und Source-Ownership einer historischen Revision sind
getrennt:

| Objekt | Runtime-/Datenowner | Migrationsquelle | Entscheidung |
| --- | --- | --- | --- |
| fünf `statistical_*`-/Mappingtabellen | `statistics` | Hostrevisionen `0016`, `0035` | Daten und IDs unverändert weiterverwenden; historische Dateien vorerst im Host belassen. |
| `cache_versions` | Host | `0015`, zusätzlich Seed in gemischter `0016` | kein Statistics-Schema- oder Migrationseigentum ableiten. |
| `analysis_areas` (nur Übergangslesen in `0035`) | `analysis-areas` | adoptierte Analysis-Areas-Historie | keine neue Statistics-Abhängigkeit; Upgrade hat die FK-Kopplung bereits entfernt. |
| `city_metrics` | Legacy-Datenhaltung, keine aktive Domain | Hostrevision `0008` | ORM/Runtime-Kopplung ist mit #219 entfernt; Tabelle und Migration bleiben unverändert erhalten. |

Eine Adoption von `0016` durch Statistics würde die Modulmigration Host-
`cache_versions` verändern. Eine Adoption von `0035` würde im Downgrade eine fremde
Analysis-Areas-Tabelle verändern. Beides widerspricht der aktuellen Ownership-Regel.
Die sichere Ausnahme ist deshalb, diese veröffentlichten Dateien unverändert in der
Host-Lineage zu behalten und die bereits eindeutige Tabellenownership im Modul zu
deklarieren. Passive Discovery funktioniert bei deaktiviertem Statistics-Modul,
weil die historische Quelle Host-owned bleibt; Daten werden beim Disable weder
gedowngradet noch entfernt. Neue Statistics-Migrationen benötigen eine neue
namespacete Modulrevision am dann aktuellen globalen Head und dürfen nur eigene
Tabellen verändern.

## Sichere PR- und Issue-Reihenfolge

| Reihenfolge | Scope | Abhängigkeit / Exit-Kriterium |
| --- | --- | --- |
| 0 | Dieses Inventar, Ownership-Entscheidung und aktuelle Contract-Baseline | keine Runtimeänderung; Review vor Migration |
| 1 | [#219](https://github.com/oklabflensburg/open-city-planner/issues/219): verwaistes `CityMetrics`-ORM und Account-Service-Kopplung entfernen | FK-Verhalten charakterisiert; Migration und Tabelle bleiben erhalten |
| 2 | [#220](https://github.com/oklabflensburg/open-city-planner/issues/220): neues Statistics-Release für Import, Settings, Job-Registry und ausschließlich eigene Writes | baut auf 0/1; kein Analysis-Areas-Import, neue SemVer-Version und Modul-CI |
| 3 | [#221](https://github.com/oklabflensburg/open-city-planner/issues/221): notwendige Statistics-API-/Admin-Frontend-Contributions anhand explizit charakterisierter Produktverträge | baut auf 2; keine Rekonstruktion entfernter Routen ohne bestätigten Vertrag |
| 4 | [#222](https://github.com/oklabflensburg/open-city-planner/issues/222): immutable Bundle-/Registry-Aktualisierung und Disable/Re-enable-End-to-End-Gate mit Analysis Areas 1.5.3 | baut auf veröffentlichtem Modulrelease aus 2/3 |
| 5 | [#223](https://github.com/oklabflensburg/open-city-planner/issues/223): finaler Host-Audit, schärfere negative Guards und #128-Abschluss | baut auf 1–4; Polygon-Code wird explizit an #129 übergeben |

Schritt 1 entfernt weder Daten noch API. Der PostgreSQL-Regressionstest beweist vor
dem Cleanup den FK-Vertrag und danach den vollständigen Account-Delete-Flow. Die
Statistics-Modularbeit beginnt anschließend im bestehenden externen Repository
statt mit einer zweiten Hostimplementierung.

## Gates je Schritt

- Host: Ruff, Pytest, Modul-/Architecture-Contracts und Alembic-Preflight; bei
  Persistence-Änderungen Upgrade, gezielter Downgrade und erneutes Upgrade.
- Statistics-Release: eigene Backend-/Frontend-Tests, Host-Contract-Test,
  reproduzierbares `.ocp`, annotierter Tag und immutable Registry-SHA-256.
- Integration: Analysis Areas 1.5.3 plus neue Statistics-Version mit Summary 200,
  Series 200, SSR-Detailseite und Playwright.
- Lifecycle: disabled ohne API-/Frontend-/Job-Beiträge, passive History und Daten
  erhalten, Re-enable ohne Reinstall.
- Final: Security-/Supply-Chain-/Deployment-Gates sowie negative Guards gegen neue
  Statistics-/Analytics-Fachimplementierung im Host.

## Bekannte Einschränkungen

- Statistics 0.2.0 ist bewusst read-only; die alte Flensburg-Importstrecke und ihre
  Verwaltungsoberfläche sind aktuell nicht verfügbar.
- Historische `/api/v1/analytics/**`-, `/vergleich`- und
  `/verwaltung/kennzahlen`-Verträge wurden vor diesem Audit bewusst aus dem
  Slim-Host entfernt. Ihre mögliche Wiedereinführung ist Produktumfang, nicht
  notwendige Kompatibilitätsarbeit für bestehende aktuelle Clients.
- Der Name `PolygonAnalyticsPort` kann bei der Polygon-Externalisierung überprüft
  werden. Eine reine Umbenennung in #128 hätte keinen Ownershipgewinn und würde den
  bewiesenen Analysis-Areas-Vertrag unnötig ändern.
