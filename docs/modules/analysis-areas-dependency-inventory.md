# Analysis Areas: Abhängigkeitsinventar

Stand: 2026-08-29 · finaler Ownership-Cutover

Dieses Inventar klassifiziert die nach dem Cutover verbleibenden Verträge. Die
öffentlichen URLs und die physische Tabelle `analysis_areas` bleiben unverändert;
Backend, Frontend und Migrationsquelle gehören ausschließlich zum externen Modul.

## Ownership-Matrix

| Bestandteil / Consumer | Klassifikation | Ziel in #107 |
| --- | --- | --- |
| Gebietsidentität, UUID, Slug, Name, Typ und Hierarchie | gehört zu `analysis-areas` | Domain-/API-Verträge und Query-Service des Moduls |
| `analysis_areas`-Tabelle, PostGIS-Geometrie, Zentroid und OSM-Provenienz | gehört zu `analysis-areas` | unveränderte Tabelle, module-owned SQLAlchemy-Metadaten |
| Gebietsliste, Detail, Lookup, GeoJSON und Sitemap-Metadaten | gehört zu `analysis-areas` | Application/Persistence/API des Moduls |
| OSM-Gebietssynchronisierung und Wikidata-Anreicherung | gehört zu `analysis-areas` | ausschließlich externes Modul; kein Host-Fallback |
| `area_statistics` und Statistikschemas | `analysis-areas` konsumiert fremden Vertrag | Compatibility-Adapter, Ownership bleibt Statistics (#128) |
| Polygonliste und `polygon_analysis_areas`-Zuordnung | `analysis-areas` konsumiert fremden Vertrag | Compatibility-Adapter, Ownership bleibt Polygons (#129) |
| Analytics/Comparison und POI-Aggregationen | `analysis-areas` konsumiert fremden Vertrag | Compatibility-Adapter, spätere Statistics-/Analytics-Migration (#128) |
| Map Preview, ETag und Bild-Cache | Host-/Plattform-Primitive | öffentlicher `MapPreviewPort`; Renderer bleibt fachneutral |
| Public Query Guard, DB-Timeout-Erkennung und Response-Limits | Host-/Plattform-Primitive | Host-Adapter; keine Sicherheitslogik im Fachmodul dupliziert |
| Redis-Verbindung und globale Cache-Versionen | Host-/Plattform-Primitive | öffentliche Cache-Ports; Modul besitzt nur Gebietscache-Policy |
| Assistant und Search | Host-Consumer der öffentlichen Gebiets-HTTP-API | reduzierte Consumer-DTOs in `app.integrations.external_analysis_areas` |
| Statistics, Analytics, Polygons und Social | Nachbardomänen mit dokumentiertem DB-Vertrag | primitive SQL-Projektionen/DTOs; kein Foreign ORM |
| `/gebiete` und `/gebiete/:slug` samt SEO/SSR | gehört zu `analysis-areas` | Frontend-Layer des Moduls bei unveränderten URLs |
| globale Layout-, SEO-, API- und Kartenprimitives | Host-/Plattform-Primitive | über öffentliche Nuxt-Autoimports beziehungsweise Map SDK konsumiert |
| `/vergleich` und allgemeine GIS-Shell | externe Domänen konsumieren `analysis-areas` | bleiben Host-/Legacy-Consumer bis ihrer eigenen Migration |

## Festgehaltene HTTP-Verträge

Alle folgenden GET-Routen bleiben unter `/api/v1/analysis-areas` erhalten:

- Liste, GeoJSON und Sitemap
- Detail per UUID und per Slug
- Social Preview einschließlich `ETag`, `304` und `Cache-Control`
- Polygon-, Statistics-, Analytics- und Comparison-Kompatibilitätsrouten

Die Pilotmigration führt keinen `/api/v1/modules/analysis-areas`-Ersatzprefix ein.
Slug-Vergleich, Fehlerstatus, Hierarchie und JSON-Feldnamen bleiben unverändert.

## Persistenz und verbleibende Consumer

Die historische Alembic-History bleibt unverändert. Die module-owned Adoption-
Registrierung deklariert nur Ownership-Metadaten; sie führt keine Migration aus
und erstellt, kopiert, benennt oder löscht keine Fachdaten. Der allgemeine
Migrations-Preflight bleibt dabei unverändert wirksam.

Direkte Imports aus `app.modules.analysis_areas` oder Foreign-ORM-Imports aus
`ocp_module_analysis_areas` existieren in Host-Fachservices nicht. Assistant und
Search verwenden die öffentliche HTTP-API. Die noch notwendigen Statistik-,
Analytics-, Polygon- und Social-Abfragen sind explizite, reduzierte SQL-
Projektionen auf bereits dokumentierte Nachbartabellen. Direkte externe
Modulimporte bleiben auf Integrationstests und E2E-Seeding begrenzt.
