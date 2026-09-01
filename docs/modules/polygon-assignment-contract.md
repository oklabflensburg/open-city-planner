# Öffentlicher Polygon-Assignment-Vertrag

Seit Backend-SDK `1.12.0` können vertrauenswürdige In-Process-Module einen
vollständigen Area-Geometriesnapshot an die Polygon-Domäne übergeben. Die
Polygon-Domäne berechnet und persistiert daraus die Zuordnungen zu den vorhandenen
`user_polygons`.

Module lösen den Vertrag ausschließlich über `context.services` auf:

- Service-ID: `platform.polygon-assignment`
- Service-Version: `1`
- Contract: `PolygonAssignmentPort`
- Operation: `refresh_assignments(session, request)`

## Request und Geometrie

`PolygonAssignmentRequest.areas` ist ein unveränderliches Tuple mit höchstens
5.000 `PolygonAssignmentArea`-Werten. Jeder Wert enthält:

- `external_id`: kanonische, stabile UUID des Area-owning Moduls,
- `selection_group`: fachneutraler, stabiler Gruppenschlüssel,
- `geometry_wkb`: nicht leere EWKB-Bytes einer Flächengeometrie in EPSG:4326.

IDs müssen im Snapshot eindeutig sein. Die Area-Referenz muss in derselben
Datenbanktransaktion bereits persistiert sein. Unbekannte Referenzen sowie leere,
nicht-flächige oder nicht in EPSG:4326 vorliegende Geometrien werden vor der
Assignment-Mutation abgelehnt.

`selection_group` bildet die historische Auswahl je Gebietsebene fachneutral ab.
Decken mehrere gelieferte Areas derselben Gruppe den Punkt auf der Oberfläche
eines Polygons ab, gewinnt die geometrisch kleinste Area; bei gleicher Fläche
entscheidet die externe UUID stabil. Unterschiedliche Gruppen können jeweils eine
Zuordnung zum selben Polygon erzeugen.

No `UserPolygon` ORM object crosses the boundary. Auch Assignment-ORM-Objekte,
interne Polygon-IDs und konkrete Relationstabellen sind kein Teil des Contracts.

## Scope und stale cleanup

Der Request ist immer ein vollständiger Snapshot. Der Command berechnet den
gesamten Polygon-Zuordnungszustand aus genau den gelieferten Areas. Zuordnungen,
die nicht mehr im Sollzustand vorkommen, werden entfernt. Dadurch bilden sowohl
Geometrieänderungen als auch entfernte Areas stale cleanup ab; ein leerer Snapshot
entfernt alle bestehenden Area-Zuordnungen.

Die räumliche Semantik bleibt kompatibel zum historischen Sync:

1. Polygongeometrien werden mit `ST_MakeValid` normalisiert.
2. Der Zuordnungspunkt ist `ST_PointOnSurface`.
3. Eine Area muss diesen Punkt mit `ST_Covers` abdecken.
4. Die Überlappungsquote wird in EPSG:25832 aus Schnittfläche geteilt durch
   Polygonfläche berechnet.

## Ergebnis und Idempotenz

`PolygonAssignmentResult` liefert ausschließlich nichtnegative, generische Counts:

- `processed_polygons`
- `created_assignments`
- `updated_assignments`
- `removed_assignments`
- `unchanged_assignments`

Der Service gleicht den Soll- und Istzustand differenziell ab. Derselbe Request
erzeugt keine Duplikate, ersetzt keine unveränderten Zeilen und liefert diese beim
Folgelauf als unverändert zurück.

## Transaktion

Die übergebene `AsyncSession` und ihre Transaktion gehören dem Aufrufer. Der Port
öffnet keine zweite Session und führt weder `commit()` noch `rollback()` aus.
Area-State-Update, Assignment-Aktualisierung und weitere transaktionale Schritte
können daher gemeinsam committed oder vollständig zurückgerollt werden.

`create_test_module_context()` registriert unter derselben Service-ID und Version
einen `FakePolygonAssignments`. Der Fake speichert Requests und liefert ein
deterministisches Result, benötigt aber keine Datenbank oder Spatial Engine.
