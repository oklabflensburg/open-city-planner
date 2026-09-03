# Slim-Host-Extraktionsinventar

Stand: 2026-09-02

## Ausgangslage und Sicherung

Die Extraktion basiert auf `origin/staging/epic-91-modular-host` bei Commit
`410e9ba5dff2e3ed702d1a4ced95a5e5524cb52e`. Der lokale Referenz-Tag
`pre-slim-host-functional-baseline` zeigt unverändert auf diesen Commit.

Das vorbestehende, nicht eingecheckte WIP im ursprünglichen Worktree
`/home/awendelk/git/open-city-map2` wurde vor der Extraktion unverändert gesichert:

- Patch: `/home/awendelk/git/slim-host-worktree-baseline.patch`
- Status: `/home/awendelk/git/slim-host-worktree-baseline.status`
- SHA-256 des Patches: `7e9c9c0b81632e44a9f427418d2d57ec196756c5177aa609155c155346b9b74b`

Die eigentliche Arbeit findet im separaten Worktree
`/home/awendelk/git/open-city-planner-slim` auf
`refactor/slim-domain-free-host` statt. Am ursprünglichen WIP wurden weder Reset,
Restore, Clean noch Stash ausgeführt.

## Zielbild und Eigentum

| Bereich | Klassifikation | Ergebnis |
| --- | --- | --- |
| FastAPI-/Nuxt-Laufzeit, Health, Security Header, Konfiguration | `HOST_CORE` | bleibt im Host |
| Auth, Benutzer, Rollen, Berechtigungen, MFA und OAuth einschließlich Mastodon-SSO | `HOST_CORE` | bleibt im Host |
| Modul-Discovery, Installer, Runtime, Registry, SDK, Settings, Migration Coordinator | `HOST_CORE` | bleibt im Host |
| Events, Scheduler, Cache, HTTP, Logging, Tracing, DB-Sessions und Storage-Ports | `HOST_CORE` | bleibt im Host |
| Generische Polygone, CRUD, Verzeichnis, Karten-Auswahl und Polygon-Metrik-Port | `HOST_CONTRACT` | bleibt als neutrale Plattformfähigkeit |
| Generische Backend-/Frontend-/Map-/UI-/Sitemap-Beiträge | `HOST_CONTRACT` | bleibt als Erweiterungsfläche |
| Benachrichtigungen, gelesen/ungelesen, Präferenzen und Folgen generischer Ressourcen | `HOST_CORE` | bleibt ausdrücklich im Host |
| Lokale OSM-Snapshots, neutrale Objektabfrage, Provenienz und OSM-Ports | `HOST_CONTRACT` | bleibt; fachliche Ableitungen gehören in Module |
| Analysis Areas einschließlich Seiten, Router, Stores und Built-in-Modul | `MOVE_TO_MODULE` | aus der Host-Laufzeit entfernt; externes Modul ist Nachfolger |
| Kommunale Statistics-, Superset- und Zeitreihen-Laufzeit | `MOVE_TO_MODULE` | aus API, Domain-Services, Import-Jobs, UI und Deployment entfernt; ein neutraler Read-only-SDK-Adapter liest die erhaltenen Tabellen für bestehende Module |
| Analytics-, Vergleichs- und Standortanalyse | `MOVE_TO_MODULE` | aus API, Services, Stores, Seiten und Komponenten entfernt |
| Intelligente Suche und Assistant einschließlich Provider-Konfiguration | `REMOVE` | vollständig aus Host-Laufzeit und Deployment entfernt |
| Social Publishing einschließlich Mastodon-Outbox, Screenshots und Admin-UI | `REMOVE` | entfernt; Mastodon-SSO bleibt Auth-Funktion |
| Wikidata-Anreicherung und Wikidata-Linkaufbereitung | `REMOVE` | entfernt; rohe OSM-Snapshots bleiben neutral |
| Historische Statistics-, City-Metrics- und Social-Publishing-Tabellen | `DATA_SHELL` | ORM-Metadaten und veröffentlichte Migrationen bleiben zur verlustfreien Bestandsführung |
| Adoptierte Analysis-Areas-Migrationen `0014`, `0023`, `0025`, `0032` | `MOVE_TO_MODULE` | IDs und Kanten unverändert, aber ausschließlich aus dem installierten Modul passiv discoverbar; spätere Hostrevisionen bauen weiter darauf auf |

## Audit-Matrix der extrahierten Fachbereiche

Dateimuster bezeichnen die vollständig bewerteten ehemaligen Implementierungs-
gruppen; einzelne historische Migrationen und ORM-Dateien sind darunter separat
als `DATA_SHELL` ausgewiesen.

| Domäne | Alte Backend-Dateien | Alte Frontend-Dateien | Tabellen / Migrationen | Routes | Events / Scheduler | Benötigte Host-Ports | Ziel und Status | Risiko / Behandlung |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ANALYSIS_AREAS` | `app/modules/analysis_areas/**`, `api/osm.py`-Gebietsfilter, `cli/{sync_analysis_areas,set_area_wikidata,sync_wikidata}.py` | `frontend-modules/analysis-areas/**`, Analysis-Area-Komponenten/-Typen | `analysis_areas`, `polygon_analysis_areas`; `0014`, `0023`, `0025`, `0032` bleiben unverändert | `/api/v1/analysis-areas/**`, `/gebiete/**` entfernt | Gebietssync/-Reconcile und Wikidata-Jobs aus Host entfernt | DB, Cache, HTTP, Scheduler, Events, Map Preview, OSM Snapshot, Polygon Query/Identity/Spatial Match/Analytics, Statistics Read | Modul `analysis-areas`; `REMOVED_FROM_HOST`, extern wieder eingeführt | Hoch: Migrationskette und Daten; durch Data Shell, Paritätsprüfung und externes Lifecycle-Gate geschützt |
| `SEARCH` | `api/search.py`, `schemas/search.py`, `services/search_{catalog,executor,interpreter}.py` | `components/search/**`, `stores/search.ts`, `types/search.ts` | keine eigenen Tabellen | `/api/v1/search/**` entfernt | keine Host-Jobs; Suchanreicherung entfernt | HTTP, Public Query, Cache; spätere Suchindex-Ports separat entwerfen | Modul `search`; `MODULE_NOT_YET_REINTRODUCED` | Mittel: Such- und Deep-Link-Verhalten vorübergehend nicht verfügbar |
| `COMPARISON` | Vergleichsanteile in `api/analytics.py`, `services/{comparables,analytics}.py` | `pages/vergleich.vue`, `stores/comparison.ts`, `components/compare/**` | keine exklusiven Tabellen | `/vergleich`, Vergleichs-Analytics entfernt | keine | Polygon Query/Analytics; fachliche Referenzdaten durch Modul | Modul `comparison`; `MODULE_NOT_YET_REINTRODUCED` | Mittel: frühere Vergleichsansicht fehlt absichtlich |
| `ASSISTANT` | `api/assistant.py`, `schemas/assistant.py`, `services/assistant*.py` | Assistant-Shell/-Interaktionen | keine fachlich erforderliche Tabelle | `/api/v1/assistant` entfernt | Provider-Lifecycle entfernt | HTTP, Permissions, Public Query, Events; LLM-Vertrag gehört ins Modul | Modul `assistant`; `MODULE_NOT_YET_REINTRODUCED` | Hoch: Kosten, PII und Provider-Secrets; sämtliche Host-Konfiguration entfernt |
| `STATISTICS` | `api/data_sources.py`, `schemas/statistics.py`, `services/{area_statistics,flensburg_statistics_import,flensburg_superset}.py`, Import-CLI | `pages/verwaltung/kennzahlen.vue`, `AreaStatistics.vue` | `statistical_datasets`, `statistical_metrics`, `external_area_mappings`, `statistical_observations`, `statistical_import_runs` bleiben | Datenquellen-/Statistics-Hostroutes entfernt | Flensburg-Importtimer entfernt | versionierter `StatisticsQueryPort`; vorübergehend read-only aus Data Shell | Modul `statistics`; Runtime `REMOVED_FROM_HOST`, Modul noch nicht eingeführt | Hoch: Datenverlust und Referenzmodul-Kompatibilität; keine Drops, kein Import/Write im Host |
| `SOCIAL` | `services/{admin_social,social_*}.py`, Publisher-CLI, Social-Anteile in `api/admin.py` | `pages/admin/social.vue`, `useSocialPublishing.ts`, Middleware | `social_publication_outbox`, `social_publications`, `social_publishing_settings` bleiben | `/api/v1/admin/social/**` entfernt | Social-Outbox-/Publisher-Events und systemd-Timer entfernt | HTTP, Scheduler, Notifications, Storage, Permissions | Modul `social-publishing`; `MODULE_NOT_YET_REINTRODUCED` | Hoch: externe Veröffentlichungen und Secrets; Data Shell bewahrt Historie, Mastodon-SSO bleibt Auth |
| `ANALYTICS_DOMAIN` | `api/analytics.py`, `schemas/analytics.py`, `services/{analytics,location_analytics,comparables,city_metrics}.py` | `stores/analytics.ts`, Markt-/Standort-/Verteilungs-Komponenten | `city_metrics` bleibt Data Shell; Polygon-Kerndaten bleiben | `/api/v1/analytics/**` und fachliche Polygon-Analytics-Routen entfernt | fachliche Invalidierungen entfernt | neutraler PolygonScope-, Query- und Analytics-Port | getrennte spätere Analytics-/Comparison-Module; `MODULE_NOT_YET_REINTRODUCED` | Mittel: Dashboards fehlen; neutrale Flächenmetriken bleiben |
| `OSM_DOMAIN` | Gebietsableitung, Wikidata-Enrichment und fachliche POI-Auswertung aus OSM-API/-Import/-Postprocessing entfernt | Analysegebiets-Layer, POI-Auswertungsansichten und Wikidata-Linkdarstellung entfernt | `osm_features`, `polygon_osm_sources`, `osm_sync_state` bleiben Host-Contract | generischer OSM-Viewport/-Detailzugriff bleibt; Gebietsfilter entfernt | generischer Snapshot-Import bleibt, fachliche Postprocessing-Schritte entfernt | OSM Snapshot/Feature Access, HTTP, Events | mehrere fachlich zugeschnittene OSM-/Search-/Analysis-Module statt Monster-Modul; `REMOVED_FROM_HOST` | Hoch: Provenienz und Imports; rohe Snapshots bleiben unverändert zugänglich |

Notifications wurden in derselben Inventur als `NOTIFICATIONS` bewertet und
bleiben mit `notifications`, `notification_preferences` und
`notification_subscriptions`, API, SSE/Delivery und generischen Resource-IDs im
Host. Polygon Directory bleibt nach Entfernung von Branchen-/Gebietsfiltern als
fachneutrale öffentliche Polygon-Query im Host.

## Bewusst verlorene Host-Funktionen

Ein Host ohne installierte Fachmodule bietet keine Gebietsseiten, Gebietssuche,
Gebietsvergleiche, kommunale Statistikansichten, Markt-/Standortanalysen,
Assistant-Antworten, Social-Publishing-Verwaltung oder Wikidata-Anreicherung mehr.
Die bisherigen Routen `/gebiete`, `/vergleich`, `/admin/social`,
`/verwaltung/kennzahlen`, `/api/v1/analytics`, `/api/v1/search`,
`/api/v1/assistant` und `/api/v1/data-sources` gehören nicht mehr zum Hostvertrag.

Erhalten bleiben die Karte, generische Polygonansichten und -bearbeitung,
Authentifizierung, Administration, Benachrichtigungen, OSM-Referenzdaten sowie die
Modulplattform. Ein Modul kann eigene Routen, UI, Kartenebenen, Jobs,
Berechtigungen und Migrationen beitragen.

## Daten- und Migrationsstrategie

Diese Änderung löscht keine produktiven Daten und führt keine destruktive Migration
ein. Die vier adoptierten Analysis-Areas-Revisionsdateien werden ohne Änderung
ihrer IDs, Kanten oder Operationen exklusiv vom externen Modul geliefert. Die noch registrierten
ORM-Modelle für historische Statistics-, City-Metrics- und Social-Publishing-Tabellen
sind ausschließlich ein Persistence-/Compatibility-Shell; kein Host-Router, Worker
oder UI besitzt diese Fachdomänen mehr. Eine spätere physische Datenmigration oder
Tabellenbereinigung benötigt einen eigenen Rollout-, Backup- und Rollback-Plan.

## Schutz vor Rückkopplung

`backend/tests/test_slim_host_boundaries.py` blockiert bekannte entfernte
Backend-Runtimepfade und private Domain-Imports. Der Frontend-Guard
`frontend/tests/slim-host-boundaries.test.ts` blockiert die entfernten Routen,
Stores und Komponenten in der Runtime. Positive Tests stellen gleichzeitig sicher,
dass Notifications und generische Map-/UI-Beiträge erhalten bleiben.

## Externes Analysis-Areas-Modul

Die vorherige Built-in-Implementierung wurde durch das eigenständige Repository
`oklabflensburg/ocp-module-analysis-areas` ersetzt. Der Cutover-Workflow baut und
installiert das Bundle, prüft dessen historische Migrationen sowie öffentliche
SDK-/Port-Grenzen und startet die übernommenen Charakterisierungstests. Die
zugehörige Extraktionsänderung wurde mit Pull Request
`oklabflensburg/ocp-module-analysis-areas#9` zusammengeführt.
Den abschließenden Treffer-, Ownership-, Bundle- und Paritätsabgleich dokumentiert
der [Analysis-Areas-Host-Cleanup](analysis-areas-host-cleanup.md).

## Noch bewusst generische Kompatibilität

Einige öffentliche SDK-Datentypen für Statistik bleiben vorerst als versionierter
Vertrag erhalten. Ein schreibfreier Kompatibilitätsadapter projiziert ausschließlich
die erhaltenen Tabellen in diese DTOs, weil das externe Analysis-Areas-Modul aus
PR #9 diesen veröffentlichten Port noch voraussetzt. Import, Scheduler, API, Cache-
Policy und UI sind nicht Teil dieses Adapters und bleiben aus der Host-Runtime
entfernt. Ebenso bleiben historische Audit-, Notification- und OSM-Daten lesbar,
ohne dass daraus eine aktive fachliche Statistics-, Social- oder Wikidata-Runtime
entsteht. Diese Grenze verhindert Datenverlust und erlaubt externen Modulen einen
kontrollierten Übergang.
