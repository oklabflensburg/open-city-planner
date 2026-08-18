# Stündliche OpenStreetMap-Synchronisierung

Stand dieser Betriebsanleitung: 18. August 2026. Sie beschreibt den versionierten
Stadtplaner-Prozess für Schleswig-Holstein. Befehle, die Produktionsdaten ändern,
sind bewusst nicht automatisch bei einem Deployment aktiv.

## 1. Überblick und Architektur

```text
Geofabrik Schleswig-Holstein PBF (initial)
        ↓ osm2pgsql --create --slim --output flex
osm_import.osm_features_stage + osm_middle.*
        ↓ osm2pgsql-replication init am exakten PBF-Zeitstempel
offizielle OSM-Minuten-Diffs, stündlich gesammelt
        ↓ atomisches Postprocessing
public.osm_features
        ↓
Analysis Areas + Polygon-Zuordnung + Cache-Versionen
        ↓
FastAPI / Redis / Nuxt
```

Es gibt keinen stündlichen Full-Reimport. Der Timer holt alle seit dem letzten
erfolgreichen Lauf fehlenden Minuten-Diffs nach. `Persistent=true` holt einen
verpassten Timer nach einem Neustart nach; `flock` verhindert Parallelimporte.

Die Produktionsumschaltung ist Blue/Green auf Tabellenebene: osm2pgsql baut und
aktualisiert ausschließlich die internen Schemas `osm_import` und `osm_middle`.
`public.osm_features` wird erst nach einem vollständigen Import- beziehungsweise
Diff-Chunk in einer PostgreSQL-Transaktion aktualisiert. Ein fehlgeschlagener
Full-Import löscht die öffentlich gelesene Tabelle daher nicht.

## 2. Inventur des bestehenden Systems

Die Inventur auf dem Entwicklungs-/Betriebshost ergab:

| Bereich | Tatsächlicher Stand vor dieser Änderung |
| --- | --- |
| Datenbank | `open_city_map` auf `localhost:5432` |
| Anwendungsschema | `public` |
| Anwendungsrolle | `postgres` laut `backend/.env` |
| PostgreSQL | 18.4 |
| PostGIS | 3.6.4; außerdem `hstore` 1.8 vorhanden |
| osm2pgsql | 2.1.1 auf dem Entwicklungshost; 1.11.0 auf dem Produktionshost |
| Osmium | 1.18.0 |
| PyOsmium | Ubuntu-Paket 4.0.2 |
| Psycopg | `python3-psycopg2` 2.9.10 |
| Linux-User | `oklab` und der nologin-Systemuser `osm` existieren; `stadtplaner` fehlt |
| PostgreSQL-Rollen | `oklab`, `osm`, `postgres` existieren |

Vorher existierte nur ein einmaliger klassischer `pgsql`-Import:

- `public.osm_stage_point`: 28.847 Zeilen
- `public.osm_stage_line`: 24.595 Zeilen
- `public.osm_stage_polygon`: 69.687 Zeilen
- `public.osm_stage_roads`: 1.987 Zeilen
- `public.osm_features`: 69.185 Zeilen
- `public.osm2pgsql_properties`: `output=pgsql`, `updatable=false`,
  `current_timestamp=2026-08-12T18:46:23Z`

Die bestehende Datenbank belegte 99 MiB, davon `osm_features` 32 MiB und die vier
alten Stage-Tabellen zusammen rund 46 MiB. Das sind Bestandswerte, keine Prognose
für den neuen Slim-Import.

Es gab keine Nodes-/Ways-/Relations-Middle-Tabellen, keinen Replikationsstatus,
keine Lua-Datei und keinen OSM-Timer. Dieser Bestand kann deshalb nicht mit
`--append` weitergeführt werden. Ein neuer Slim-Import ist zwingend.

Die Anwendung liest nur `public.osm_features` mit dem Primärschlüssel
`(osm_type, osm_id)`, JSONB-Tags, EPSG:4326-Geometrie und `imported_at`.
`polygon_osm_sources` dedupliziert bewusst übernommene Stadtplaner-Flächen gegen
OSM. Ein OSM-Delete entfernt nicht die lokale Stadtplaner-Fläche und nicht ihren
gespeicherten Quell-Snapshot.

Damit sind die OSM-relevanten Anwendungstabellen `osm_features`,
`polygon_osm_sources`, `analysis_areas`, `polygon_analysis_areas`,
`cache_versions` und neu `osm_sync_state`. Pro-Objekt-Felder `osm_version` und
`osm_timestamp` existieren im Anwendungsvertrag nicht; statt einer uneinheitlichen
Teilbefüllung hält `osm_sync_state` den belastbaren globalen Replikationsstand.

Nach OSM-Änderungen sind tatsächlich erforderlich:

1. Staging-Daten in `osm_features` abgleichen, einschließlich Deletes.
2. Flensburger OSM-Analysegebiete und räumliche Polygon-Zuordnungen aktualisieren.
3. die persistenten Cache-Versionen `osm`, `analytics`, `analysis-areas` erhöhen.

Es existieren keine OSM-Materialized-Views und kein Suchindex. Redis ist nur ein
wiederberechenbarer Read-Cache. Es wird weder `FLUSHDB` noch `FLUSHALL` verwendet;
alte, versionsgebundene Keys laufen per TTL/LRU aus. Das Postprocessing erzeugt
keine Social-Publishing-Events und keinen Objekt-Auditspam.

Vorhandene systemd-Units sind
`stadtplaner-flensburg-statistics-sync.{service,timer}` und
`stadtplaner-social-publisher.{service,timer}`. Letztere verwendet bereits
`oklab`; deshalb ist dieser User auch für OSM gewählt. Der Systemuser `osm` hat
kein nutzbares Home für `.pgpass`. Die ältere Statistik-Unit nennt dagegen den
auf diesem Host fehlenden User `stadtplaner` und einen abweichenden Pfad; sie ist
kein verlässliches Muster für die neue Unit.

## 3. Quellenentscheidung

Initialextract:

```text
https://download.geofabrik.de/europe/germany/schleswig-holstein-latest.osm.pbf
```

Replikationsquelle:

```text
https://planet.openstreetmap.org/replication/minute
```

Der Timer läuft stündlich, nutzt aber den minütlichen Stream. Dadurch werden alle
fehlenden Diffs in kleineren Schritten nachgezogen. Die Geofabrik-Regional-Diffs
sind laut Anbieter nur täglich und können echte stündliche Aktualität nicht
liefern. osm2pgsql dokumentiert ausdrücklich, dass ein regionaler Extract mit
Planet-Diffs aktualisiert werden kann. Wichtig sind dabei zwei Schutzmaßnahmen:

- `init --start-at <PBF-Zeitstempel>` startet nicht fälschlich bei „jetzt“.
- Der Flex-Style schreibt nur Objekte, deren Bounding Box die großzügige
  Schleswig-Holstein-Box berührt; PostGIS beschränkt danach exakt auf die aktuelle
  administrative Relation mit `ISO3166-2=DE-SH`.

Planet-Diffs enthalten weltweite Änderungen. Obwohl die Output-Tabelle räumlich
begrenzt bleibt, wachsen die Slim-Middle-Tabellen langfristig durch geänderte
Objekte außerhalb des Initialextracts. Das ist die bewusste Gegenleistung für die
offizielle, stündlich aktuelle Quelle. Größe und Wachstum müssen überwacht werden;
ein periodischer sicherer Full-Reimport setzt sie zurück. Eine Alternative mit
kleineren Middle-Tabellen wäre ein passender minütlicher Regionalprovider, wäre
aber nicht die hier geforderte offizielle OSM-Replikationsquelle.

Primärquellen:

- <https://osm2pgsql.org/doc/manual.html#updating-an-existing-database>
- <https://osm2pgsql.org/doc/man/osm2pgsql-replication-2.1.1.html>
- <https://download.geofabrik.de/technical.html>
- <https://download.geofabrik.de/europe/germany/schleswig-holstein.html>

Extract und Startsequenz passen zusammen, weil nicht die Sequenz eines anderen
Providers übernommen wird: Der offizielle Stream ermittelt seine eigene Sequenz
aus dem im PBF gespeicherten UTC-Snapshot-Zeitpunkt. Überlappende Diffs sind
unproblematisch; eine Lücke zwischen PBF und „jetzt“ wäre es nicht.

## 4. Voraussetzungen und Kapazität

Auf jedem Zielhost zuerst die echten Versionen erfassen:

```bash
osm2pgsql --version
osmium --version
psql --version
python3 --version
dpkg-query -W osm2pgsql osmium-tool python3-pyosmium python3-psycopg2
```

Installation auf Ubuntu/Debian:

```bash
sudo apt update
sudo apt install osm2pgsql osmium-tool python3-pyosmium python3-psycopg2 postgresql postgis curl
```

`osm2pgsql-replication update --help` muss `--post-processing` und
`status --json` unterstützen. Die installierte Version 2.1.1 tut dies. Beim
Upgrade müssen Release Notes und die Hilfe erneut geprüft werden; Skriptparameter
werden nicht aus einer fremden Versionsdokumentation übernommen.

Vor Import und regelmäßig im Betrieb:

```bash
df -h /data/stadtplaner
df -i /data/stadtplaner
sudo -u postgres psql open_city_map -c \
  "SELECT pg_size_pretty(pg_database_size(current_database()));"
```

Bei der Inventur waren 55 GiB frei. Das ist kein dauerhaft garantierter Wert und
muss unmittelbar vor dem Import neu geprüft werden. Slim-Tabellen benötigen ein
Mehrfaches des 150-MiB-PBFs; zusätzlich wachsen sie durch Planet-Diffs. Kein
Flat-Node-File verwenden: Für einen regionalen Import wäre dessen planetweite
Größe unverhältnismäßig.

## 5. Benutzer, PostgreSQL und Dateirechte

Die Unit verwendet den existierenden Linux-User `oklab` und die vorhandene Gruppe
`www-data`. Die bestehende PostgreSQL-Rolle `osm` ist auf dem inspizierten Host
derzeit Superuser; das ist für den Dauerbetrieb unnötig. Nach einem Staging-Test
soll sie auf Login plus Eigentum an den Import-Schemas reduziert werden. Die
Anwendungsrolle benötigt weiterhin Schreibrechte auf Anwendungstabellen für das
transaktionale Postprocessing.

Einmalige Vorbereitung als Administrator:

```bash
sudo -u postgres psql open_city_map <<'SQL'
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS osm_import AUTHORIZATION osm;
CREATE SCHEMA IF NOT EXISTS osm_middle AUTHORIZATION osm;
GRANT CONNECT ON DATABASE open_city_map TO osm;
ALTER ROLE osm NOSUPERUSER NOCREATEDB NOCREATEROLE;
SQL

sudo install -d -o oklab -g www-data -m 0750 \
  /data/stadtplaner \
  /data/stadtplaner/extracts \
  /data/stadtplaner/replication \
  /data/stadtplaner/tmp \
  /data/stadtplaner/logs
sudo install -d -o root -g www-data -m 0750 /etc/stadtplaner
sudo install -o root -g www-data -m 0640 \
  deploy/osm-sync.env.example /etc/stadtplaner/osm-sync.env
```

Der Importjob selbst führt kein `CREATE SCHEMA` aus und benötigt kein
datenbankweites `CREATE`-Recht. Er prüft vor dem Import, dass PostGIS vorhanden
ist und beide Import-Schemas der Rolle `osm` gehören. Nach dem Flex-Import liest
er die Anwendungsrolle ohne Passwortausgabe aus `backend/.env` und gewährt ihr
nur `USAGE` sowie `SELECT` auf `osm_import`. Default Privileges erhalten diesen
Zugriff auch dann, wenn osm2pgsql die Stage-Tabelle bei einem Reimport neu anlegt.
Bei abweichender Konfiguration kann `OSM_APPLICATION_DB_ROLE` explizit gesetzt
werden. Die Anwendung erhält keinen Zugriff auf `osm_middle`.

Die DB-Verbindung für osm2pgsql kommt aus libpq-Variablen im Environment. Das
Passwort gehört in `/home/oklab/.pgpass`, nicht in `ExecStart` oder Git:

```text
127.0.0.1:5432:open_city_map:osm:<PASSWORT>
```

```bash
sudo chown oklab:oklab /home/oklab/.pgpass
sudo chmod 0600 /home/oklab/.pgpass
```

Vor dem Download prüft das Initialskript die Anmeldung ohne interaktiven Prompt.
`password authentication failed` bedeutet, dass Eintrag, Rolle oder Passwort
nicht übereinstimmen; `pg_isready` allein prüft keine erfolgreiche Anmeldung.

Die Backend-Verbindung für das fachliche Postprocessing bleibt zentral in
`backend/.env`; sie wird nicht in `osm-sync.env` dupliziert. Keine neuen
öffentlichen Ports sind erforderlich, nur ausgehendes HTTPS. Die sichtbare Karte
behält unabhängig von dieser Pipeline die vorhandene OpenStreetMap-Attribution;
ODbL-Hinweise dürfen nicht entfernt werden.

## 6. Konfiguration

`/etc/stadtplaner/osm-sync.env` enthält Pfade, DB-Namen und nicht geheime
Parameter. Auf dem Zielhost insbesondere prüfen:

```bash
sudoedit /etc/stadtplaner/osm-sync.env
sudo -u oklab env OSM_ENV_FILE=/etc/stadtplaner/osm-sync.env \
  /opt/git/open-city-planner/scripts/osm/status.sh
```

Die versionierte Vorlage verwendet den konsistenten Deployment-Pfad
`/opt/git/open-city-planner`. Ältere Units im Repository enthalten teilweise
`/opt/stadtplaner` oder den nicht vorhandenen Linux-User `stadtplaner`; diese
Werte dürfen nicht auf die OSM-Unit übertragen werden.

## 7. Initialextract prüfen und importieren

Migrationen zuerst gegen die Anwendungsdatenbank einspielen:

```bash
cd /opt/git/open-city-planner/backend
.venv/bin/alembic upgrade head
sudo -u postgres psql open_city_map -c \
  'GRANT SELECT ON TABLE public.osm_sync_state TO osm;'
```

Der eng begrenzte Grant erlaubt dem mit der Importrolle laufenden Statusskript,
den publizierten Datenstand zu lesen. Die Rolle `osm` erhält dadurch keine
Schreibrechte auf Anwendungstabellen.

Der Initialimport lädt PBF und MD5 nicht nach `/tmp`, prüft den Hash, zeigt mit
`osmium fileinfo` Bounding Box und Header und bricht ohne Replikationszeitstempel
ab. Er verwendet denselben exklusiven Lock wie der Updatejob. Danach erstellt er
einen updatefähigen Flex-Import mit ausdrücklich `--slim` und niemals `--drop`.

```bash
cd /opt/git/open-city-planner
sudo -u oklab env OSM_ENV_FILE=/etc/stadtplaner/osm-sync.env \
  scripts/osm/initial-import.sh
```

Der maßgebliche Importbefehl im Skript ist:

```bash
osm2pgsql --create --slim \
  -d "$PGDATABASE" -U "$PGUSER" -H "$PGHOST" -P "$PGPORT" \
  --prefix stadtplaner_osm \
  --schema osm_import --middle-schema osm_middle \
  --output flex --style scripts/osm/osm.lua \
  --cache 1024 \
  /data/stadtplaner/extracts/schleswig-holstein-latest.osm.pbf
```

Der Flex-Style erzeugt `osm_import.osm_features_stage`. osm2pgsql erzeugt zudem
`osm_middle.osm2pgsql_properties` sowie unter dem Prefix `stadtplaner_osm` die
Slim-/Middle-Tabellen in `osm_middle`. Die alten `public.osm_stage_*`-Tabellen
sind für die neue Pipeline bedeutungslos und werden erst nach erfolgreichem
Produktions-Cutover und separatem Backup bewusst entfernt.

Der Style bleibt mit osm2pgsql 1.11 kompatibel und verlässt sich im Slim-Modus
auf dessen automatisch erzeugten ID-Index. `create_index='primary_key'` darf hier
nicht verwendet werden; diese Option wird erst ab osm2pgsql 2.1 unterstützt.

## 8. Replikation initialisieren und manuell testen

Das Initialskript liest diesen Wert direkt aus dem PBF:

```bash
osmium fileinfo -g header.option.osmosis_replication_timestamp \
  /data/stadtplaner/extracts/schleswig-holstein-latest.osm.pbf
```

Der daraus gebildete Init-Befehl lautet:

```bash
osm2pgsql-replication init \
  -d open_city_map -U osm -H 127.0.0.1 -P 5432 \
  -p stadtplaner_osm --schema osm_import --middle-schema osm_middle \
  --server https://planet.openstreetmap.org/replication/minute \
  --start-at '<PBF_TIMESTAMP>'
```

Niemals `--start-at now` verwenden. `--osm-file` wird hier ebenfalls nicht
verwendet, weil es die tägliche Geofabrik-URL aus dem Header wählen würde.

Status und Properties prüfen:

```bash
sudo -u oklab env OSM_ENV_FILE=/etc/stadtplaner/osm-sync.env scripts/osm/status.sh
psql open_city_map -c \
  "TABLE osm_middle.osm2pgsql_properties;"
psql open_city_map -c \
  "SELECT count(*) FROM osm_import.osm_features_stage; SELECT count(*) FROM osm_features;"
```

Vor Installation des Timers genau einen manuellen Update-Lauf durchführen:

```bash
sudo -u oklab env OSM_ENV_FILE=/etc/stadtplaner/osm-sync.env scripts/osm/update.sh
```

`osm2pgsql-replication` ergänzt intern `--append --slim`. Der Wrapper übergibt
dieselben Flex-/Style-/Schema-Parameter wie beim Erstimport und gibt sie nicht
widersprüchlich doppelt an. Das Postprocessing erhält Sequenz und Timestamp. Bei
einem Fehler verschiebt osm2pgsql-replication den Replikationsstand nicht; ein
erneuter Lauf ist idempotent.

Bei osm2pgsql-replication 1.11 muss `--schema osm_import` zusätzlich hinter dem
Argumenttrenner `--` stehen. Nur dort wird es an den gestarteten osm2pgsql-Prozess
weitergereicht. Fehlt es, versucht osm2pgsql während des Append-Laufs im Schema
`public` zu arbeiten und scheitert bei einer minimal privilegierten Importrolle.

## 9. Postprocessing und Konsistenz

`app.cli.postprocess_osm` führt in einer Transaktion aus:

1. aktuelle Landesgrenze `boundary=administrative`, `ISO3166-2=DE-SH` verlangen;
2. neue/geänderte Punkte und Flächen nach `public.osm_features` upserten;
3. nicht mehr vorhandene oder aus Schleswig-Holstein verschobene OSM-Quellen
   aus `osm_features` entfernen;
4. Flensburger Analysegebiete und Polygon-Gebietszuordnungen idempotent erneuern;
5. `osm`, `analytics` und über den Gebietssync `analysis-areas` invalidieren;
6. Sequenz, OSM-Datenzeit und Change-Counts in `osm_sync_state` speichern;
7. alles gemeinsam committen.

Mit `--verbose` meldet die CLI Beginn und Abschluss jeder Phase inklusive
verstrichener Zeit und Change-Counts. Die versionierten Import-/Update-Skripte
aktivieren diesen Modus standardmäßig; Secrets oder vollständige SQL-Texte werden
nicht ausgegeben.

`polygon_osm_sources` und `user_polygons` werden bei OSM-Deletes nicht gelöscht.
Dadurch bleibt eine bewusst übernommene lokale Fläche erhalten; ihr OSM-Link hat
danach lediglich keine aktuelle Zeile in `osm_features`. Create, Tag-/Namens- und
Geometrieänderungen werden durch den nächsten Diff-Lauf übernommen.

## 10. systemd installieren

```bash
sudo cp deploy/systemd/stadtplaner-osm-update.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now stadtplaner-osm-update.timer
systemctl list-timers stadtplaner-osm-update.timer
systemctl cat stadtplaner-osm-update.service
```

`OnUnitActiveSec=1h` plant relativ zum letzten Start; `Persistent=true` holt nach
einer Downtime einen Lauf nach. Der kleine zufällige Delay verteilt externe
Abrufe. Der Service ist `oneshot` und braucht keinen Restart-Loop. Der nächste
Timerlauf übernimmt temporäre Netzwerk- oder DB-Fehler.

Der Wrapper sperrt `/data/stadtplaner/update.lock`. Ein zweiter Start meldet
`OSM_UPDATE_SKIPPED reason=already_running` und importiert nicht parallel.

## 11. Logs, Status und Monitoring

```bash
journalctl -u stadtplaner-osm-update.service --since today
journalctl -u stadtplaner-osm-update.service -f
systemctl status stadtplaner-osm-update.timer
sudo -u oklab env OSM_ENV_FILE=/etc/stadtplaner/osm-sync.env scripts/osm/status.sh
```

Jeder Lauf loggt Start, Status/Sequenz/Timestamp davor und danach, Laufzeit,
Postprocessing-Counts, Warnungen und Erfolg/Fehler. Passwörter werden nicht
ausgegeben. `osm_sync_state` liefert den tatsächlich publizierten Datenstand:

```sql
SELECT sequence, osm_timestamp AS osm_datenstand,
       last_success_at AS letzte_synchronisierung,
       now() - osm_timestamp AS lag,
       CASE
         WHEN now() - osm_timestamp <= interval '3 hours' THEN 'HEALTHY'
         WHEN now() - osm_timestamp <= interval '12 hours' THEN 'LAGGING'
         ELSE 'FAILED'
       END AS health
FROM osm_sync_state WHERE singleton;
```

Empfohlene Alarme: zwei aufeinanderfolgende fehlgeschlagene Units oder Lag über
drei Stunden. Nach zwölf Stunden ist der Status `FAILED`. Bei vorhandenem
Prometheus-/Node-Exporter diese Werte ohne Objekt- oder Sequenz-Labels abbilden:

- `osm_replication_lag_seconds`
- `osm_replication_last_success_timestamp`
- `osm_replication_duration_seconds`
- `osm_replication_failures_total`

Das Repository besitzt derzeit kein zentrales Metrics-/OnFailure-System; deshalb
erfindet diese Änderung keines. Die Werte sind aus DB und Journal ableitbar.

## 12. Validierung und Tests

Nach Full-Import und erstem Update:

```bash
psql open_city_map <<'SQL'
SELECT count(*) FROM osm_features;
SELECT osm_type, osm_id, tags->>'name', imported_at
FROM osm_features
WHERE tags->>'ISO3166-2'='DE-SH' OR lower(tags->>'name')='flensburg'
ORDER BY imported_at DESC NULLS LAST LIMIT 20;
SELECT count(*) AS invalid_sample
FROM (SELECT geometry FROM osm_features TABLESAMPLE SYSTEM (1) LIMIT 10000) sample
WHERE NOT ST_IsValid(geometry);
SQL
```

Keinen stündlichen vollständigen `ST_IsValid`-Scan ausführen. Während eines
Updates einen normalen GIS-Request messen; SELECTs dürfen verfügbar bleiben.

Vor Produktion in einer separaten DB kontrollierte OSM-XML-/OSC-Fixtures testen:

| Fall | Erwartung |
| --- | --- |
| Create | neue Stage- und `osm_features`-Zeile nach Postprocessing |
| Modify | Tags, Name oder Geometrie geändert; `imported_at` erneuert |
| Delete | OSM-Zeile entfernt, lokale `user_polygons`-Übernahme bleibt |
| Cache | Cache-Version `osm` steigt; neuer API-Request liefert neuen Stand |
| Postprocess-Fehler | Unit non-zero; Replikationssequenz bleibt stehen |
| Parallelstart | zweiter Lauf wird sauber übersprungen |
| Neustart | DB-State bleibt erhalten, Timer setzt fort |
| drei Stunden Pause | ein Lauf zieht alle fehlenden Minuten-Diffs nach |

Während der Implementierung wurde Flex mit osm2pgsql 2.1.1 in getrennten,
anschließend gelöschten Testschemas real ausgeführt: Create erzeugte Node, Way
und Relation; Append änderte den Node, legte einen neuen Node an und entfernte
den gelöschten Way. Die dauerhafte Datenbank blieb dabei unverändert.

Einen realen OSM-Create/Modify/Delete nicht durch willkürliche Änderungen an OSM
testen. Stattdessen Test-DB und lokale Fixtures oder ohnehin geplante, fachlich
richtige Community-Edits verwenden und deren veröffentlichten Diff abwarten.

## 13. Performance und Wartung

Nach dem Staging- und dem ersten Produktionslauf echte Werte ergänzen:

```bash
psql open_city_map <<'SQL'
SELECT n.nspname, c.relname, pg_size_pretty(pg_total_relation_size(c.oid)) AS size,
       s.n_live_tup, s.n_dead_tup, s.last_autovacuum, s.last_autoanalyze
FROM pg_class c
JOIN pg_namespace n ON n.oid=c.relnamespace
LEFT JOIN pg_stat_user_tables s ON s.relid=c.oid
WHERE n.nspname IN ('osm_import','osm_middle','public')
  AND (c.relname LIKE 'stadtplaner_osm%' OR c.relname IN ('osm_features','osm_features_stage'))
ORDER BY pg_total_relation_size(c.oid) DESC;
SQL
```

Es liegen noch keine ehrlichen Messwerte für initiale Importdauer, typische
Updatezeit, neue DB-Größe oder Slim-Größe vor; sie werden nicht erfunden. Journal
und obige Query sind die Messquellen. Autovacuum/Autoanalyze zunächst beobachten
und tabellenspezifisch erst nach Messung tunen. Keine stündlichen Full-ANALYZE-
Läufe und kein automatisches `VACUUM FULL`. GiST-/ID-Indizes werden beim Import
angelegt und nicht pro Update neu erstellt.

`Nice=10` und moderate Best-Effort-I/O-Priorität reduzieren Konkurrenz zur API.
Wenn ein Update regelmäßig nahe eine Stunde dauert, zuerst Download, osm2pgsql,
Postprocessing, Locks, RAM und I/O getrennt messen; nicht Parallelität zulassen.

## 14. Fehlerbehebung

### Keine Replikationsinformation

```bash
osmium fileinfo /data/stadtplaner/extracts/schleswig-holstein-latest.osm.pbf
psql open_city_map -c "TABLE osm_middle.osm2pgsql_properties;"
osm2pgsql-replication status -d open_city_map -U osm -p stadtplaner_osm \
  --schema osm_import --middle-schema osm_middle --json
```

Fehlt der PBF-Timestamp, nicht bei „jetzt“ starten. Einen aktuellen, vollständigen
PBF erneut laden.

### Datenbank zu alt / Diffs nicht mehr verfügbar

Sequenz niemals manuell vorspulen. Aktuellen PBF laden, Full-Reimport in den
internen Schemas durchführen und Replikation neu initialisieren.

### Slim-Tabellen fehlen

`updatable=false` oder fehlende `osm_middle.stadtplaner_osm_*` bedeuten, dass
`--slim` fehlte oder `--drop` verwendet wurde. Full-Reimport ist erforderlich.

### Flex-Style geändert

Reine Tagfilter-Erweiterungen können vorhandene, seitdem unveränderte Objekte
nicht rückwirkend erzeugen. Bei Schema-, Geometrie- oder Relevanzänderungen daher
Full-Reimport; Style und Skripte gemeinsam aus demselben Git-Commit deployen.

### Permission denied

Service-User, `0750`-Datenverzeichnisse, `.pgpass` mit `0600`, Schema-Owner,
Backend-Environment und absoluten Lua-Pfad prüfen.

### GIS zeigt alte Daten

In dieser Reihenfolge prüfen: Replikationsstatus → `osm_sync_state` → konkrete
`osm_features`-Zeile → Analysis-Area-Sync → `cache_versions` → API → Frontend.

### Netzwerk- oder DB-Ausfall

Die Unit endet non-zero. Der Replikationsstand wird bei fehlgeschlagenem
Postprocessing nicht fortgeschrieben. Nach Behebung denselben Lauf wiederholen.

## 15. Recovery und sicherer Full-Reimport

Ein normaler Ausfall von fünf Stunden oder zwei Tagen wird durch einen Lauf
nachgezogen, solange die Quelle die Diffs vorhält. Ein Full-Reimport ist nötig,
wenn Diffs nicht mehr verfügbar sind, Middle-Tabellen fehlen/beschädigt sind oder
der Flex-Vertrag inkompatibel geändert wurde.

Runbook mit geringer Downtime:

1. Timer stoppen, laufende Unit vollständig enden lassen.
2. Datenbankbackup einschließlich `public`, `osm_import` und `osm_middle` erstellen.
3. aktuellen PBF neben der alten Datei laden und prüfen.
4. `initial-import.sh` ausführen; `public.osm_features` bleibt bis zum abschließenden
   Postprocessing verfügbar.
5. Counts, DE-SH-Grenze, Geometrie-Stichprobe und API prüfen.
6. manuellen `update.sh`-Lauf bis zum aktuellen Stand ausführen.
7. Timer wieder starten und Status prüfen.

```bash
sudo systemctl stop stadtplaner-osm-update.timer
systemctl is-active stadtplaner-osm-update.service
sudo -u postgres pg_dump -Fc open_city_map \
  -f /sicherer/backup-pfad/open_city_map-before-osm-reimport.dump
sudo -u oklab env OSM_ENV_FILE=/etc/stadtplaner/osm-sync.env \
  /opt/git/open-city-planner/scripts/osm/initial-import.sh
sudo -u oklab env OSM_ENV_FILE=/etc/stadtplaner/osm-sync.env \
  /opt/git/open-city-planner/scripts/osm/update.sh
sudo systemctl start stadtplaner-osm-update.timer
```

OSM-Roh- und Stagingdaten sind reproduzierbar. Nicht ohne Backup reproduzierbar
sind Benutzerflächen, `polygon_osm_sources`, manuelle Analysis-Area-/Wikidata-
Entscheidungen, Auth-, Statistik- und Social-Daten. Ein normales vollständiges
DB-Backup enthält auch Replikationsproperties und `osm_sync_state`.

## 16. Produktions-Cutover-Checkliste

- [ ] echte Paketversionen und `osm2pgsql-replication --help` geprüft
- [ ] mindestens mehrere GiB Reserve plus Wachstumsreserve gemessen
- [ ] PostGIS vorhanden; Import-Schemas gehören der minimalen DB-Rolle
- [ ] Datenverzeichnisse und `.pgpass` besitzen restriktive Rechte
- [ ] Alembic-Migration `20260818_0024` eingespielt
- [ ] PBF-Hash, Header, Bounding Box und Timestamp geprüft
- [ ] Full-Import mit `--slim`, ohne `--drop`, erfolgreich
- [ ] DE-SH-Relation in Stage vorhanden
- [ ] Replikation am PBF-Timestamp initialisiert
- [ ] manueller Update- und Postprocessing-Lauf erfolgreich
- [ ] Create/Modify/Delete/Cache/Parallel-/Restart-/Catch-up-Tests in Staging bestanden
- [ ] API während Update erreichbar und Antwort aktuell
- [ ] systemd-Unit und Timer installiert, aktiviert und im Journal sichtbar
- [ ] Lag-Alarm und Disk-/DB-Größenmonitoring eingerichtet
- [ ] Backup und Full-Reimport mindestens einmal in Staging geprobt

Öffentlich nur formulieren: „Die OpenStreetMap-Daten werden stündlich
synchronisiert. Je nach Verfügbarkeit der Quellsysteme kann sich die
Aktualisierung verzögern.“ Wenn ein Datenstand angezeigt wird, muss er aus
`osm_sync_state.osm_timestamp` stammen, nicht aus dem aktuellen Serverzeitpunkt.
