# Öffentlicher OSM-Snapshot- und Ereignisvertrag

Seit Backend-SDK `1.11.0` können vertrauenswürdige In-Process-Module den
Host-eigenen OSM-Stand lesen und auf einen erfolgreich veröffentlichten neuen Stand
reagieren. Der Host kennt dabei weder konkrete Consumer-Module noch deren
Fachmodelle.

## Snapshot-Service

Module lösen den Vertrag ausschließlich über `context.services` auf:

- Service-ID: `platform.osm-snapshot-query`
- Service-Version: `1`
- Contract: `OsmSnapshotQueryPort`

Der Plattform-Service erfordert keine Modulabhängigkeit im Manifest. ID und Version
müssen trotzdem immer exakt angegeben werden. Die Methode `list_features(session,
query)` nimmt an der vom Consumer übergebenen Session teil und liefert nur immutable
DTOs, niemals Host-ORM-Instanzen.

`OsmSnapshotQuery` unterstützt OSM-Typen (`node`, `way`, `relation`),
Geometriearten (`point`, `area`), erforderliche Tag-Schlüssel, Tag-Werte und eine
optionale EPSG:4326-Bounding-Box. Mehrere Tagfilter gelten gemeinsam (AND), mehrere
Werte innerhalb eines Filters alternativ (OR). Jede Abfrage hat ein Limit von 1 bis
500; der Standard ist 100. Pro Query sind höchstens 20 eindeutige erforderliche
Tag-Schlüssel und 20 eindeutige Tagfilter erlaubt, pro Tagfilter höchstens 50
eindeutige Werte.
Der Bounding-Box-Filter prüft räumliche Überlappung. Benötigt ein Consumer eine
exakte topologische Beziehung, wertet er diese anhand der gelieferten EWKB-Geometrie
selbst aus.

Die Reihenfolge ist stabil nach `(osm_type, osm_id)`. `next_cursor` ist exklusiv und
wird unverändert in die nächste Query übernommen. Eine leere Seite besitzt keinen
Folgecursor.

`OsmFeatureSnapshot` enthält ausschließlich:

- `osm_type` und `osm_id` als stabile OSM-Identität,
- eine defensive, schreibgeschützte Kopie der String-Tags,
- Geometrie als immutable EWKB-Bytes in EPSG:4326,
- die Bounding Box `(west, south, east, north)` in EPSG:4326,
- `imported_at` mit Zeitzone.

Namen, Verwaltungsstufen, Gebietstypen oder andere fachliche Interpretationen
werden aus den Tags vom jeweiligen Consumer abgeleitet. Dadurch enthält der Host
keine Kenntnis eines konkreten Gebietsmoduls.

## Abschlussereignis

Nach erfolgreicher OSM-Nachverarbeitung veröffentlicht der Host:

- Eventname: `osm.postprocessing-completed`
- Eventversion: `1`
- Payload: `sequence`, `osm_timestamp`, `inserted`, `updated`, `deleted`

Der Outbox-Eintrag wird vor dem Commit in derselben Datenbanktransaktion wie
OSM-Snapshot, Sync-State und Cache-Generationen angelegt. Ein Rollback veröffentlicht
daher kein Ereignis. Subscriber sehen das Ereignis erst nach dem Commit; ein späterer
Handlerfehler kann den bereits committed OSM-Stand nicht zurückrollen.

Die Zustellung erfolgt über die bestehende Outbox mindestens einmal je Handler.
Mehrere Subscriber werden separat nachverfolgt; nur fehlgeschlagene Handler werden
wiederholt und gegebenenfalls als Dead Letter markiert. Consumer müssen deshalb
idempotent sein und können dafür die stabile `EventEnvelope.event_id` speichern.
Handler abonnieren ausschließlich die unterstützte Eventversion und dürfen keine
sofortige, genau-einmalige Zustellung voraussetzen.

Ein vollständig isolierter Testcontext registriert einen `FakeOsmSnapshotQueries`
unter derselben Service-ID und Version. Externe Module können damit Snapshot-Abfrage
und Eventregistrierung testen, ohne Host-Services, ORM-Modelle oder Infrastruktur zu
importieren.
