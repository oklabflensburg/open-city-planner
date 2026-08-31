# Lokale OpenStreetMap-Daten

Stadtplaner fragt OpenStreetMap-Informationen beim Auswählen einer Fläche bedarfsgesteuert ab. Die primäre Quelle ist die lokale PostGIS-Tabelle `osm_features`. Bei einer bewussten Übernahme werden nur ausgewählte öffentliche Ausgangswerte und ein begrenzter Quell-Snapshot gespeichert; die Oberfläche verändert keine OSM-Daten.

Zusätzlich stellt die Hauptkarte relevante lokale OSM-Punkte und -Flächen dynamisch für den aktuellen Kartenausschnitt dar. Dieser Viewport-Pfad verwendet niemals den optionalen Overpass-Fallback.

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

## Quellenübergreifendes Filtermodell

Die fachlichen Filter `area_sizes`, `floors`, `categories`, `occupancy_statuses`, `business_structures` und `sources` werden sowohl an die Stadtplaner- als auch an die OSM-Abfrage übergeben. Innerhalb einer Dimension gilt OR, zwischen Dimensionen AND. `osm_categories` steuert davon getrennt die Umfeldlayer wie ÖPNV, Parken oder Kultur.

Für jede fachliche Dimension gilt derselbe öffentliche Vertrag: Ein fehlender Query-Parameter bedeutet „alle Werte“, der alleinstehende Sentinel `NONE` bedeutet „keine Werte“. `NONE` darf nicht mit realen Werten kombiniert werden. Die Oberfläche startet deshalb mit sichtbar ausgewählten Optionen, lässt die vollständige Auswahl zur kompakten Standard-URL weg und schreibt eine vollständig abgewählte Gruppe ausdrücklich als `NONE`. Fehlende Angaben bleiben in der ungefilterten Gesamtsicht enthalten; bei einer Teilmenge werden sie nicht geschätzt und erfüllen den Filter nicht.

OSM-Tags werden in `app/services/osm_canonical.py` serverseitig auf die bestehenden Stadtplaner-Kategorien normalisiert. Das Mapping basiert auf dem lokal importierten Flensburger Tagbestand. Beispiele:

| Stadtplaner-Kategorie | OSM-Tags, auszugsweise |
| --- | --- |
| `fashion` | `shop=clothes`, `shoes`, `fashion`, `jewelry` |
| `food` | `shop=supermarket`, `bakery`, `butcher`, `chemist`, `cosmetics` |
| `electronics` | `shop=electronics`, `computer`, `mobile_phone` |
| `furniture` | `shop=furniture`, `interior_decoration`, `kitchen` |
| `garden` | `shop=garden_centre`, `doityourself`, `sports`, `outdoor`, `florist` |
| `warehouse` | `shop=department_store`, `mall`, `variety_store` |
| `gastronomy` | `amenity=restaurant`, `cafe`, `fast_food`, `bar`, `pub` |
| `services` | `shop=hairdresser/beauty/tattoo/massage/...`, `office=*`, `craft=*`, `amenity=bank/pharmacy` |
| `other` | sonstige vorhandene `shop=*`-Werte |

Lifecycle-Tags behalten dabei ihre frühere Branche: `disused:shop=clothes` ist beispielsweise `fashion` mit Status `VACANT`. Nicht geschäftsbezogene OSM-Objekte erhalten keine Canonical Category und bleiben als Umfeld erhalten.

Für Etagen wird ausschließlich ein einfaches, numerisches `level` verwendet: negative Werte werden `UG`, `0` wird `EG`, positive Werte werden `OG`. `building:levels` beschreibt das Gebäude und wird niemals als Lage des Geschäfts interpretiert. Fehlendes oder mehrdeutiges `level` bleibt unbekannt. Leerstand wird konservativ aus `shop=vacant`, `disused:shop=*` oder einem gewerblich eingeordneten `disused=yes` erkannt; alle anderen Objekte bleiben `UNKNOWN`, nicht automatisch `OCCUPIED`.

OSM-Geometrien erhalten im Viewport eine als `mapped_area_m2` bezeichnete projizierte Kartierungsfläche. Sie wird nicht als Verkaufsfläche ausgegeben und derzeit keiner S/M/L/XL-Klasse zugeordnet: Im Projekt existieren weder belastbare Verkaufsflächen-Tags noch zentral belegte Quadratmetergrenzen für diese Klassen. Ein aktiver Größen- oder Betriebsformfilter schließt deshalb OSM-Geschäftsobjekte ohne dieses fachliche Attribut aus, während Umfeldobjekte sichtbar bleiben.

Die Normalisierung wird bewusst in der BBOX-beschränkten SQL-Abfrage berechnet. Damit spiegeln Upserts in `osm_features` sofort neue oder geänderte Tags wider und es gibt keine veralteten materialisierten Felder. GiST auf `geometry`, GIN auf `tags` sowie die BTree-Verknüpfungsindizes bleiben die gemessene Indexbasis; zusätzliche Indizes wurden ohne belastbaren Nutzen nicht angelegt.

`polygon_osm_sources` bildet die Deduplication ab. Sind Stadtplaner und OSM gleichzeitig aktiv, gewinnt die gepflegte Stadtplaner-Fläche und verknüpfte OSM-Objekte werden aus Karte, OSM-Counts und Facetten entfernt. Wird ausdrücklich nur OSM gewählt, bleibt das OSM-Original sichtbar. Raw Tags werden ausschließlich im Detail-Endpunkt freigegeben; der Kartenrequest enthält nur normalisierte Summary-Felder.

## Dynamischer Kartenausschnitt

`GET /api/v1/osm/features` erwartet West-, Süd-, Ost- und Nordgrenze sowie den MapLibre-Zoom. Die Abfrage baut mit `ST_MakeEnvelope` eine Geometrie in EPSG:4326 auf und verwendet zuerst `geometry && bbox`, anschließend `ST_Intersects`. Ungültige Importgeometrien werden ausgelassen. Der GiST-Index bleibt damit nutzbar; die Geometriespalte wird in der Filterbedingung nicht transformiert.

Unter Zoom 11 werden keine interaktiven OSM-Features geliefert. Zoom 11–12 beschränkt sich auf benannte wichtige POIs, Zoom 13–14 ergänzt weitere POIs und ab Zoom 15 kommen relevante Flächen hinzu. Reine Gebäude werden nur bei aktivem Gebäudelayer und ab Zoom 17 geliefert. Polygongeometrien werden bei niedrigeren Detailstufen topologieerhaltend vereinfacht. Pro Antwort gelten maximal 2.500 Features und eine zoomabhängige BBOX-Grenze; `truncated` fordert bei Überschreitung zum Hineinzoomen auf.

Die kleine Viewport-Antwort enthält nur stabile OSM-ID, Umfeld- und Canonical Category, normalisierten Status bzw. Etage, kartierte Fläche, Name, Primärtyp und Geometrie. Vollständige freigegebene Sachdaten und Raw Tags werden erst nach Auswahl über `GET /api/v1/osm/features/{osm_type}/{osm_id}` geladen. Antworten besitzen einen kurzen öffentlichen Cache, ETag und den lokalen OSM-Importzeitpunkt.

`natural=peninsula` ist zentral von der interaktiven Pipeline ausgeschlossen. Die JSONB-Bedingung `tags->>'natural' IS DISTINCT FROM 'peninsula'` greift in der räumlichen Query vor Kategorisierung, Quoten, Geometrieausgabe und Redis. Eine zentrale Python-Policy fängt alternative Row-Provider defensiv ab; sie betrifft ausdrücklich nicht `natural=wood`, `natural=water`, `natural=coastline`, `place=island` oder `place=islet`. Direkte Details bleiben über den allgemeinen Detail-Endpunkt abrufbar, die Übernahme als Stadtplaner-Fläche antwortet dagegen mit `OSM_FEATURE_NOT_IMPORTABLE`.

Im lokalen Bestand war Relation `14658378` („Angeln“) das einzige betroffene Objekt: Polygon, 4.648 Punkte und 96.940 Bytes GeoJSON-Geometrie. In einem betroffenen Zoom-17-Testviewport sank die Antwort von 8 auf 7 Features, von 4.738 auf 90 Geometriepunkte und von 101.857 auf 4.719 Bytes. Die Landmasse bleibt über die unabhängige VersaTiles-Basemap sichtbar; nur das zusätzliche auswählbare OSM-Overlay entfällt.

MapLibre hält je eine langlebige GeoJSON-Source für Punkte und Polygone. Punkte werden bis Zoom 14 geclustert; Kartenbewegungen aktualisieren nur `setData()`. `moveend`/`zoomend` werden entprellt, laufende Requests abgebrochen und zusätzlich durch eine Request-Generation gegen verspätete Antworten geschützt.

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

## OSM als Ausgangspunkt einer Stadtplaner-Fläche

Angemeldete Nutzer können `POST /api/v1/polygons/from-osm` mit `osm_type`, `osm_id` und optional einer Etage aufrufen. Der Server lädt Geometrie und Tags erneut aus `osm_features`; die Browserantwort des Viewport-Layers ist niemals die maßgebliche OSM-Quelle. Polygon und MultiPolygon werden vollständig übernommen. Für einen Point sucht PostGIS mit `ST_Covers` und einer deterministischen Kleinste-Fläche-Priorisierung ein umschließendes Gebäude beziehungsweise Nutzpolygon. Ohne Treffer antwortet die API mit `OSM_GEOMETRY_REQUIRED`. Erst eine ausdrücklich manuell gezeichnete Geometrie kann den Import dann abschließen; ein künstlicher Buffer wird nicht persistiert.

Die Relation `polygon_osm_sources` speichert OSM-Typ und -ID, Originalgeometrie, einen begrenzten Tag-Snapshot sowie Import- und Quelldatum. Bei einem Point-Import bleibt der POI die primäre Quelle; die als Geometriebasis gewählte umschließende OSM-Fläche wird zusätzlich als sekundäre Quelle protokolliert. Mehrere Stadtplaner-Flächen dürfen dieselbe OSM-Quelle für unterschiedliche Etagen verwenden. Eine Wiederholung derselben Quelle und Etage wird abgewiesen. Änderungen oder Löschen einer Stadtplaner-Fläche schreiben niemals nach `osm_features` zurück.

Die zentrale Leerstandserkennung übernimmt `shop=vacant` und `disused:shop=*` als `VACANT` mit Quelle `OSM`. `disused=yes` gilt nur mit Einzelhandels-/Gewerbekontext als Leerstand. `abandoned:*` bleibt bewusst `UNKNOWN`. Ändert VERWALTUNG den Status, wird die Herkunft auf `MANUAL` gesetzt; dieser Wert wird durch spätere OSM-Daten nicht still überschrieben.

## OpenStreetMap verbessern

Stadtplaner enthält weder OSM-Schreibzugriff noch OSM-OAuth-Schreibrechte oder einen eingebetteten Editor. Nach einem bewussten Klick können öffentliche Nutzer die offizielle StreetComplete-Webseite oder den iD-Editor auf `openstreetmap.org` öffnen. Der iD-Link wird nach Möglichkeit auf den repräsentativen Punkt des gewählten Objekts zentriert. Vor dem Klick entstehen keine zusätzlichen Drittanbieteranfragen.

## Administrative Analysegebiete

Analysegebiete sind keine Host-OSM-Importfunktion mehr. Tabelle, Boundary-Sync,
Wikidata-Anreicherung und die adoptierte Revision `20260814_0014` gehören zum
externen `analysis-areas`-Modul. Der Host führt nur den gemeinsamen Graphen aus:

```bash
cd backend
.venv/bin/python -m app.cli.module_migrations preflight
.venv/bin/python -m app.cli.module_migrations upgrade
```

Import und Pflege der Gebietsressourcen müssen über den dokumentierten
Betriebspfad des installierten Moduls erfolgen; im Host existiert dafür kein
Fallback-CLI.

Der Dienst sucht die Gemeinde anhand einer realen polygonalen `boundary=administrative`-Relation und leitet die nächsten zwei vorhandenen administrativen Ebenen aus dem lokalen Bestand ab. Geometrien werden mit `ST_MakeValid`, `ST_CollectionExtract(..., 3)` und `ST_Multi` normalisiert. Polygonale `place=borough/suburb/quarter/neighbourhood`-Objekte sind nur ein Fallback; Punkte werden nie gepuffert. Der Upsert ist über OSM-Typ und OSM-ID idempotent.

Im lokalen Flensburger Bestand vom 14. August 2026 wurden Relation 27020 als Gemeinde (`admin_level=6`), 13 Stadtteile (`admin_level=9`) und 37 Quartiere (`admin_level=10`) erkannt. Tarup besitzt in diesem Bestand kein administratives Level-10-Quartier. Punktförmige Ortsobjekte – darunter `place=city`, `place=suburb`, `place=neighbourhood` und das punktförmige `place=quarter` Kattloch – werden nicht als Analysefläche übernommen.

Stadtteile erhalten die Gemeinde als Parent; Quartiere werden über `ST_Covers` und die größte Schnittfläche ihrem Stadtteil zugeordnet. Stadtplaner-Polygone werden anhand von `ST_PointOnSurface` genau einem Gebiet je vorhandener Ebene zugeordnet. Diese Zuordnung wird nach Import sowie nach Erstellung oder Geometrieänderung einer Stadtplaner-Fläche aktualisiert. POIs werden nicht dupliziert, sondern für Gebietsanalysen direkt aus `osm_features` räumlich aggregiert.
