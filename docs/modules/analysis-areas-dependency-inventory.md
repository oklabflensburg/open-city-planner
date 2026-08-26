# Analysis Areas: Abhängigkeitsinventar

Stand: 2026-08-26 · Pilotmigration [#107](https://github.com/oklabflensburg/open-city-planner/issues/107)

Dieses Inventar hält die vor dem Refactoring ermittelten Produktionsverträge und
Abhängigkeitsrichtungen fest. Es ist zugleich die Grenze für die temporären
Legacy-Adapter: Die Pilotmigration ändert weder öffentliche URLs noch die
physische Tabelle `analysis_areas`.

## Ownership-Matrix

| Bestandteil / Consumer | Klassifikation | Ziel in #107 |
| --- | --- | --- |
| Gebietsidentität, UUID, Slug, Name, Typ und Hierarchie | gehört zu `analysis-areas` | Domain-/API-Verträge und Query-Service des Moduls |
| `analysis_areas`-Tabelle, PostGIS-Geometrie, Zentroid und OSM-Provenienz | gehört zu `analysis-areas` | unveränderte Tabelle, module-owned SQLAlchemy-Metadaten |
| Gebietsliste, Detail, Lookup, GeoJSON und Sitemap-Metadaten | gehört zu `analysis-areas` | Application/Persistence/API des Moduls |
| OSM-Gebietssynchronisierung und Wikidata-Anreicherung | temporäre Legacy-Abhängigkeit | bestehendes Verhalten über exakt markierte Adapter; weitere Entkopplung #127 |
| `area_statistics` und Statistikschemas | `analysis-areas` konsumiert fremden Vertrag | Compatibility-Adapter, Ownership bleibt Statistics (#128) |
| Polygonliste und `polygon_analysis_areas`-Zuordnung | `analysis-areas` konsumiert fremden Vertrag | Compatibility-Adapter, Ownership bleibt Polygons (#129) |
| Analytics/Comparison und POI-Aggregationen | `analysis-areas` konsumiert fremden Vertrag | Compatibility-Adapter, spätere Statistics-/Analytics-Migration (#128) |
| Map Preview, ETag und Bild-Cache | Host-/Plattform-Primitive | Compatibility-Adapter; Renderer bleibt fachneutral |
| Public Query Guard, DB-Timeout-Erkennung und Response-Limits | Host-/Plattform-Primitive | Host-Adapter; keine Sicherheitslogik im Fachmodul dupliziert |
| Redis-Verbindung und globale Cache-Versionen | Host-/Plattform-Primitive | bestehender Host-Adapter; Modul besitzt nur Gebietscache-Policy |
| Assistant, Search, Statistics, Polygons, Social und OSM-CLI | externe Domänen konsumieren `analysis-areas` | vorhandene Consumer bleiben in #107 als dokumentierte Legacy-Consumer; neue Pfade nutzen `analysis-areas.lookup` |
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

## Persistenz und verbleibende Legacy-Consumer

Die historische Alembic-History bleibt unverändert. Die module-owned Adoption-
Registrierung deklariert nur Ownership-Metadaten; sie führt keine Migration aus
und erstellt, kopiert, benennt oder löscht keine Fachdaten. Der allgemeine
Migrations-Preflight bleibt dabei unverändert wirksam.

Direkte ORM-Consumer außerhalb des Moduls sind Bestandscode in OSM-Import,
Statistics, Polygons, Assistant, Search, Social Publishing und administrativen
CLI-Werkzeugen. Sie werden hier nicht als neue Architektur empfohlen. Der neue
materialisierte Query-Vertrag `analysis-areas.lookup` ist der Zielpfad für deren
inkrementelle Migration in #108/#127/#128/#129.
