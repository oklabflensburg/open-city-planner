# Öffentlicher Polygon-Spatial-Match-Vertrag

Seit Backend-SDK `1.12.0` können vertrauenswürdige In-Process-Module eigene
Flächengeometrien rein lesend gegen die Host-eigenen `user_polygons` abgleichen.
Die Polygon-Domäne liefert nur immutable Match-Ergebnisse. Consumer-Module
besitzen und persistieren ihre domänenspezifischen Beziehungen selbst.

Module lösen den Vertrag ausschließlich über `context.services` auf:

- Service-ID: `platform.polygon-spatial-match`
- Service-Version: `1`
- Contract: `PolygonSpatialMatchPort`
- Operation: `match_polygons(session, request)`

## Request und Geometrie

`PolygonSpatialMatchRequest.areas` ist ein unveränderliches Tuple mit höchstens
5.000 `PolygonSpatialArea`-Werten. Jeder Wert enthält:

- `external_id`: opaque, stabiler und im Request eindeutiger Consumer-Identifier,
- `selection_group`: fachneutraler, stabiler Gruppenschlüssel,
- `geometry_wkb`: nicht leere EWKB-Bytes einer Flächengeometrie in EPSG:4326.

Der Host löst `external_id` nicht gegen eine fremde Tabelle auf. Leere,
nicht-flächige oder nicht in EPSG:4326 vorliegende Geometrien werden abgelehnt.

`selection_group` bildet die historische Auswahl je Gebietsebene fachneutral ab.
Decken mehrere gelieferte Flächen derselben Gruppe den Punkt auf der Oberfläche
eines Polygons ab, gewinnt die geometrisch kleinste Fläche; bei gleicher Fläche
entscheidet `external_id` stabil. Unterschiedliche Gruppen können jeweils einen
Match zum selben Polygon liefern.

## Result und stabile Polygon-Identität

`PolygonSpatialMatchResult.matches` ist ein unveränderliches Tuple aus
`PolygonSpatialMatch`-Werten:

- `polygon_id`: öffentliche, stabile UUID des Host-Polygons,
- `external_area_id`: unverändert zurückgegebener Consumer-Identifier,
- `selection_group`: Gruppenschlüssel der ausgewählten Fläche,
- `overlap_ratio`: Schnittfläche geteilt durch Polygonfläche oder `None` bei einer
  Polygonfläche von null.

No `UserPolygon` ORM object crosses the boundary. Interne Polygon-PKs,
SQL-Ausdrücke, Assignment-ORM-Objekte und konkrete Relationstabellen sind kein
Teil des Contracts.

## Räumliche Semantik

Die Semantik bleibt kompatibel zum historischen Sync:

1. Polygongeometrien werden mit `ST_MakeValid` normalisiert.
2. Der Zuordnungspunkt ist `ST_PointOnSurface`.
3. Eine gelieferte Fläche muss diesen Punkt mit `ST_Covers` abdecken.
4. Die Überlappungsquote wird in EPSG:25832 berechnet.
5. Pro Polygon und `selection_group` wird höchstens die kleinste passende Fläche
   geliefert.

## Read-only- und Transaktionsverhalten

Der Port liest ausschließlich `user_polygons`. Er liest keine fremden
Gebietstabellen, schreibt keine Assignment-Relation und führt weder `commit()` noch
`rollback()` aus. Zwei Consumer-Requests können sich deshalb nicht gegenseitig
persistierten Zustand löschen oder überschreiben. Gleiche Requests liefern bei
unverändertem Polygonstand dasselbe Ergebnis.

Die übergebene `AsyncSession` gehört dem Aufrufer. Ein Consumer kann Match-Ergebnis,
eigene Relation und stale cleanup anschließend innerhalb seiner eigenen
Transaktionsgrenze koordinieren.

`create_test_module_context()` registriert unter derselben Service-ID und Version
einen `FakePolygonSpatialMatches`. Der Fake speichert Requests und liefert ein
deterministisches Result, benötigt aber keine Datenbank oder Spatial Engine.
