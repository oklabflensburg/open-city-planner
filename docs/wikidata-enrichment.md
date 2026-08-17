# Wikidata-Anreicherung von Gebieten

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

Nur `AUTO_MATCHED` und `VERIFIED` werden als strukturierte, serverseitig erzeugte URLs ausgegeben. Fehlt `dewiki`, erscheint nur Wikidata. Fremde URL-Werte aus der Datenbank werden nicht gerendert.

Die Übersicht `/gebiete` und jede Detailseite `/gebiete/{slug}` verwenden denselben persistenten Zuordnungsstand. Auf Detailseiten erscheinen Wikidata und Wikipedia als weiterführende Wissensquellen; sie werden nicht mit den fachlichen GIS- und Statistik-Datenquellen vermischt. Nicht jedes lokale Quartier besitzt einen eigenen Wikidata- oder Wikipedia-Eintrag, daher bleibt der Abschnitt dort vollständig verborgen. Ein Parent-Link wird nie geerbt.

Ein manuelles Match hat `wikidata_match_source=MANUAL`, `wikidata_match_status=VERIFIED` und `wikidata_verified=true`. Der automatische Sync selektiert solche Zeilen nicht. Ändert sich der OSM-Q-ID-Tag, bleibt die manuelle Q-ID bestehen und der Status wechselt zu `CONFLICT`.

## Betrieb

```bash
python -m app.cli.sync_analysis_areas --municipality Flensburg
python -m app.cli.sync_wikidata
python -m app.cli.sync_wikidata --force
python -m app.cli.set_area_wikidata flensburg Q3798
```

Standardmäßig werden nur fehlende, nicht erfolgreiche oder nach 90 Tagen veraltete Matches geprüft. Entity- und Suchantworten liegen mit langer TTL im vorhandenen Redis; negative Antworten kürzer. Der Client setzt einen Projekt-User-Agent, begrenzt Timeout und Suchmenge und wiederholt nur Netzwerkfehler, HTTP 429 und 5xx mit Backoff.
