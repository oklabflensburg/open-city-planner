# Wikidata-Anreicherung von Gebieten

> Ownership-Hinweis: Diese Fachfunktion gehört seit dem finalen Cutover zum
> externen `ocp-module-analysis-areas`. Der Host enthält weder Implementierung
> noch CLI-Fallback; dieser Text dokumentiert Datenvertrag und bisheriges
> Verhalten für Betrieb und Nachbardomänen.

Die Verknüpfung ist ein persistenter Importprozess und kein Bestandteil eines öffentlichen Page Requests:

```text
lokale OSM-Features
  → wikidata-/wikipedia-Tags im Gebiets-Upsert
  → WikidataEnrichmentService
  → Entity-, Sitelink-, Parent- und Distanzprüfung
  → analysis_areas
  → öffentliche Area-DTOs
  → SSR-Links und JSON-LD sameAs
```

## Priorität und Veröffentlichung

1. Eine syntaktisch gültige OSM-Q-ID wird mit `wbgetentities` validiert (`OSM_WIKIDATA`, 1,00).
2. `wikipedia=de:Titel` wird über `wbgetentities&sites=dewiki` zur Q-ID aufgelöst (`OSM_WIKIPEDIA`, 0,95).
3. Die Suche verwendet Name, Parent/Gemeinde und Deutschland. Nur Kandidaten mit exaktem Label/Alias, passendem Referenzpunkt und Parent-/Ortssignal erreichen den Schwellwert 0,85 (`WIKIDATA_SEARCH`). Die produktive Distanzprüfung berechnet PostGIS mit `ST_DistanceSphere` gegen den bereits per `ST_PointOnSurface` bestimmten Gebietsreferenzpunkt. Nahezu gleich bewertete Treffer bleiben `AMBIGUOUS`.
4. Ohne eindeutigen Treffer wird `NOT_FOUND` gespeichert. Ein Quartier erbt niemals den Link seines Parents.

Ein vorhandenes, aber syntaktisch ungültiges oder mehrwertiges `wikidata`-Tag
wird als `INVALID` gespeichert und löst keine Namenssuche aus. Existiert eine
syntaktisch gültige Q-ID nicht, bleibt der Zustand `NOT_FOUND`; auch dann wird
nicht auf einen geratenen Treffer gewechselt. Wenn `wikidata` und ein deutsches
`wikipedia`-Tag auf verschiedene Entities zeigen, lautet der Zustand `CONFLICT`
und beide Links bleiben aus der öffentlichen Gebietsausgabe ausgeblendet.

Nur `AUTO_MATCHED` und `VERIFIED` werden als strukturierte, serverseitig erzeugte URLs ausgegeben. Fehlt `dewiki`, erscheint nur Wikidata. Fremde URL-Werte aus der Datenbank werden nicht gerendert.

Die Übersicht `/gebiete` und jede Detailseite `/gebiete/{slug}` verwenden denselben persistenten Zuordnungsstand. Auf Detailseiten erscheinen Wikidata und Wikipedia als weiterführende Wissensquellen; sie werden nicht mit den fachlichen GIS- und Statistik-Datenquellen vermischt. Nicht jedes lokale Quartier besitzt einen eigenen Wikidata- oder Wikipedia-Eintrag, daher bleibt der Abschnitt dort vollständig verborgen. Ein Parent-Link wird nie geerbt.

Ein manuelles Match hat `wikidata_match_source=MANUAL`, `wikidata_match_status=VERIFIED` und `wikidata_verified=true`. Der automatische Sync selektiert solche Zeilen nicht. Ändert sich der OSM-Q-ID-Tag, bleibt die manuelle Q-ID bestehen und der Status wechselt zu `CONFLICT`.

## OSM-Objekte und übernommene Flächen

Der Flex-Import speichert die Tags von Nodes, geschlossenen Ways und relevanten
Relations vollständig als JSONB in `osm_import.osm_features_stage`; das atomare
Postprocessing übernimmt sie unverändert nach `osm_features.tags`. Dadurch gehen
`wikidata` und `wikipedia` weder bei POIs noch bei Polygonen verloren.

Die OSM-Detail-API liefert daraus `external_links`. Sie akzeptiert ausschließlich
Q-IDs nach `^Q[1-9][0-9]*$` und deutsche Wikipedia-Tags; beliebige OSM-URLs und
Mehrfachwerte werden nicht in öffentliche Links umgewandelt. Bei einer Übernahme
in eine Stadtplaner-Fläche werden beide Tags zusätzlich im Snapshot der primären
`polygon_osm_sources`-Zeile gespeichert und auf `/flaechen/{slug}` angezeigt.
Der Page Request fragt weder Wikidata noch Wikipedia live ab.

Referenz-Fixture (über die OSM API am 18. August 2026 geprüft):

```text
way/37376249
name=Lutherpark
wikidata=Q19965387
wikipedia=de:Lutherpark (Flensburg)
```

## Betrieb

Gebietssync, automatische Anreicherung und manuelle Verifikation müssen über den
vom installierten Modul dokumentierten Betriebspfad ausgeführt werden. Die
früheren Host-Kommandos `app.cli.sync_analysis_areas`, `app.cli.sync_wikidata`
und `app.cli.set_area_wikidata` wurden mit der Domain-Source entfernt.

Standardmäßig werden nur fehlende, nicht erfolgreiche oder nach 90 Tagen veraltete Matches geprüft. Entity- und Suchantworten liegen mit langer TTL im vorhandenen Redis; negative Antworten kürzer. Der Client setzt einen Projekt-User-Agent, begrenzt Timeout und Suchmenge und wiederholt nur Netzwerkfehler, HTTP 429 und 5xx mit Backoff.

Das stündliche OSM-Postprocessing setzt bei geänderten Gebietstags den Prüfzeitpunkt
zurück, aktualisiert die Snapshots bereits übernommener Flächen und startet danach
die persistente Gebietsanreicherung. Manuelle Zuordnungen bleiben dabei geschützt.
