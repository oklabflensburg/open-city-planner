# Analysis Areas: Host-Cleanup und Paritätsnachweis

Stand: 2026-09-03 · Issue
[#196](https://github.com/oklabflensburg/open-city-planner/issues/196)

Diese Matrix bewertet den tatsächlich getrackten Host auf Basis der Suchbegriffe
`analysis-areas`, `analysis_areas`, `AnalysisArea`, `AnalysisAreas`, `/gebiete`,
`/api/v1/analysis-areas`, `external_analysis_areas`, `area_statistics`,
`wikidata`, `comparison` und `polygon_directory`. Generierter Bytecode und lokale
Installationsverzeichnisse sind keine Hostquellen.

## Ownership- und Paritätsmatrix

| Fundgruppe | Klassifikation | Zielzustand und Nachweis |
| --- | --- | --- |
| ehemalige Backend-Router, DTOs, ORM-Modelle, Services, Sync-/Wikidata-CLI und Jobs | `module-owned` | keine Runtimequelle mehr unter `backend/app`; OSM-Sync, Wikidata-Maintenance, Polygon-Reconcile, API und Cache-Invalidierung liegen in `ocp-module-analysis-areas` v1.5.3 und verwenden öffentliche SDK-Ports |
| ehemalige Nuxt-Routen, Store, Komponenten, Layer, Actions und API-Aufrufe | `module-owned` | keine Host-Runtimequelle mehr; `/gebiete`, SEO/Structured Data, Sitemap, Kartenbeiträge und Interaktionen kommen aus dem installierbaren Frontend-Layer |
| Revisionen `20260814_0014`, `20260817_0023`, `20260818_0025`, `20260819_0032` | `module-owned` | unveränderte Revision-IDs, Kanten und Bytes werden ausschließlich aus der passiv discoverten Modulmigrationsquelle geladen; Host-Nachfolger behalten ihre bestehenden `down_revision`-Werte |
| DB-Session, Cache-Generation, HTTP, Jobs, Events, OSM-Snapshots, Map Preview und öffentliche Query-Limits | `generic host capability` | bleiben als `ModuleContext`-/SDK-Ports; sie kennen weder Analysis-Areas-DTOs noch Tabellen |
| Module Discovery, Installer, Registry, Lockfile, Migration Coordinator sowie UI-/Map-/Sitemap-Registries | `generic host capability` | bleiben fachneutral; Beiträge existieren nur für installierte und aktivierte Module, Migrationen werden auch disabled passiv entdeckt |
| Polygon Directory, Polygon Query/Analytics/Identity/Spatial Match und Statistics Query | `owned by another domain` | bleiben neutrale bzw. fremde öffentliche Contracts; der Analysis-Areas-Consumer löst seine Fachsemantik vor dem Portaufruf selbst auf |
| `ExternalProvider`/`OcpProviderIcon` mit dem Wert `wikidata` | `generic host capability` | reine Präsentation eines vom Modul gelieferten externen Links; keine Abfrage-, Matching- oder Enrichment-Logik |
| historische fachfremde Host-Migrationen mit Analysis-Areas-Fremdschlüsseln oder Datenentkopplung | `owned by another domain` | veröffentlichte globale History bleibt unverändert; sie ist keine aktive Analysis-Areas-Runtime und wird nicht umgeschrieben |
| Contract-Fixtures, Cutover-Workflow und negative Boundary-Tests | `test/architecture guard` | explizit benannte Testdaten dürfen Modul-ID und historische Tabellen enthalten; sie werden nie von der Anwendung discoverbar gemacht |
| temporäres Löschen doppelter Hostmigrationen im CI-Checkout und Host-Dokumentation fester Gebietsseiten | `obsolete` | entfernt; exklusive Ownership ist bereits im Repository abgebildet und die Benutzerfunktion wird als Modulbeitrag dokumentiert |

## Tatsächlicher externer Stand

Der veröffentlichte Registry-Pin `analysis-areas@1.0.0` besitzt den SHA-256
`7006f31ea73f40e38f63d2065652c27ad5d3391ddcc8cfad2f149993efef3dcf`
und stammt aus Source-Commit `06afb05fed5dab8426e0e52392d3716ba46c980a`.
Er enthält API, Frontend, Map-/Sitemap-Contributions und die vier historischen
Migrationen. Der Live-Download wurde über den normalen Registry-Installer in ein
temporäres Root geprüft. Installation, disabled Lockfile, Enable-Preflight und
passive Migration Discovery sind erfolgreich; der Backend-Start ist dagegen nicht
kompatibel: v1.0.0 greift auf das entfernte `ModuleContext.statistics`-Attribut zu
und bricht bei der Registrierung mit `AttributeError` ab.

Die vollständige Sync-/Wikidata-/Polygon-Parität aus
`ocp-module-analysis-areas#5` kam erst in den nachfolgenden Releases hinzu. Der
kanonische Fachstand ist v1.5.3 auf Commit
`06a675a4237fca397b37c0aeb935ecd60557073a`; er umfasst insbesondere:

- OSM-Synchronisierung über `platform.osm-snapshot-query@1` und das Event
  `osm.postprocessing-completed@1`;
- Wikidata-Enrichment, Maintenance-Service und geplanten Refresh über HTTP-, Job-
  und Cache-Generation-Ports;
- Polygon-Zuordnung über `platform.polygon-spatial-match@1` und
  `platform.polygon-identity@1`;
- Statistikabfragen über den versionierten `statistics.query@1`-Service.

Damit ist v1.0.0 ein gültiges Installer-/Migrationsartefakt, aber weder ein
kompatibler Backend-Runtime- noch ein vollständiger Produktions-Paritätsnachweis
für #196. Das finale Gate
[#197](https://github.com/oklabflensburg/open-city-planner/issues/197) installiert
deshalb ausschließlich v1.5.3 über die Registry und prüft den vollständigen
Lifecycle gemeinsam mit dem gepinnten Statistics-Modul.

## Verhalten ohne und mit Modul

Ohne installierte beziehungsweise aktivierte Fachmodule startet der Host mit
leerem Backend-Inventar und baut das Frontend ohne `/gebiete`, Analysis-Areas-API,
Sitemap-Fetch oder Kartenbeiträge. Search, Comparison und fachliche Analytics sind
ebenfalls nicht Teil des Slim Hosts; es gibt keinen versteckten Fallback.

Nach disabled Installation bleibt die Runtime unverändert, während Alembic die
historischen Revisionen passiv aus dem Paket auflösen kann. Erst `enable` und ein
neu gerenderter Deploy-/Buildzustand registrieren API, Jobs, Events, Seiten,
Sitemap und Map. Disable entfernt diese Runtime-Contributions wieder, ohne
Migrationen aus dem Graphen zu nehmen oder Daten zu verändern.

Die vier fachlichen Revisionsdateien bleiben als bytegleiche, nicht discoverbare
Fixtures unter `backend/tests/fixtures/module_migrations/analysis_areas_history`
erhalten. Sie prüfen den verschachtelten globalen Graph und bestehende Daten; die
Host-Runtime und das Host-`alembic/versions`-Verzeichnis besitzen sie nicht.
Die regulären Required-Jobs bauen daraus deterministisch ein minimales
backend-only `.ocp`-Bundle und installieren es deaktiviert über den lokalen
Installer. Sie hängen dadurch nicht von der Live-Registry ab und prüfen dennoch
den echten Bundle-, Installer- und Migrationspfad. Dieses Fixture enthält bewusst
keine Fachruntime. Seine modulspezifischen Metadaten stehen ausschließlich in
`backend/tests/fixtures/module_migrations/analysis_areas.json`. Der generische
Builder `build_module_migration_bundle.py` kennt weder Modul-ID noch Schema,
Paket oder Revisions-Namespace und kann mit einer zweiten Fixture-Definition
dieselbe passive Bundle-Struktur für ein beliebiges anderes Modul erzeugen.
