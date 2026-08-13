# Stadtplaner einrichten: lokale OpenStreetMap-Daten

Diese Anleitung richtet den lokalen OSM-Datenbestand für Stadtplaner ein. Das Backend liest anschließend passende Points of Interest und Gebäude aus PostgreSQL/PostGIS, ohne bei jedem Polygonklick eine öffentliche Overpass-Instanz anzufragen.

Der Datenfluss ist:

```text
Geofabrik Schleswig-Holstein
        ↓
Flensburg-Extrakt mit Osmium
        ↓
osm2pgsql-Stagingtabellen
        ↓
public.osm_features
        ↓
Stadtplaner-API
```

## 1. Voraussetzungen

Benötigt werden:

- PostgreSQL mit PostGIS
- `osm2pgsql`
- `osmium-tool`
- `wget` oder `curl`
- eine ausgeführte Stadtplaner-Alembic-Migration

Unter Ubuntu/Debian können die Werkzeuge beispielsweise so installiert werden:

```bash
sudo apt update
sudo apt install osm2pgsql osmium-tool postgresql-postgis wget
```

Versionen prüfen:

```bash
osm2pgsql --version
osmium --version
psql --version
```

Die folgenden Beispiele verwenden:

```text
Datenbank: open_city_map
PostgreSQL-Host: localhost
Importbenutzer: oklab
Arbeitsverzeichnis: /var/lib/stadtplaner/osm
```

Benutzernamen, Datenbank und Pfade müssen gegebenenfalls an die Produktionsumgebung angepasst werden. Datenbankpasswörter gehören nicht in Shell-Skripte oder das Git-Repository. Für automatisierte Imports empfiehlt sich eine restriktiv lesbare `.pgpass`-Datei.

## 2. Datenbank vorbereiten

Zuerst alle Stadtplaner-Migrationen ausführen:

```bash
cd /pfad/zu/open-city-planner/backend
.venv/bin/alembic upgrade head
```

Die Migration `20260813_0009` legt `public.osm_features` an. Tabelle und Indizes prüfen:

```bash
psql --host localhost --username oklab --dbname open_city_map \
  --command '\d+ public.osm_features'
```

Benötigte Erweiterungen aktivieren. Dafür kann ein PostgreSQL-Administrator erforderlich sein:

```bash
sudo -u postgres psql --dbname open_city_map \
  --command 'CREATE EXTENSION IF NOT EXISTS postgis;'

sudo -u postgres psql --dbname open_city_map \
  --command 'CREATE EXTENSION IF NOT EXISTS hstore;'
```

Der Importbenutzer benötigt Schreibrechte auf den Stagingtabellen und `osm_features`. Wenn Migrationen und Anwendung denselben Datenbankbenutzer verwenden, sind üblicherweise keine zusätzlichen Grants nötig. Andernfalls gezielt vergeben:

```bash
sudo -u postgres psql --dbname open_city_map --command \
  'GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON public.osm_features TO oklab;'
```

## 3. Arbeitsverzeichnis anlegen

```bash
sudo install --directory --owner "$USER" --group "$USER" \
  /var/lib/stadtplaner/osm

cd /var/lib/stadtplaner/osm
```

## 4. Schleswig-Holstein herunterladen

Geofabrik veröffentlicht täglich aktualisierte regionale OSM-Auszüge:

```bash
wget --continue \
  --output-document schleswig-holstein-latest.osm.pbf \
  https://download.geofabrik.de/europe/germany/schleswig-holstein-latest.osm.pbf
```

Optional kann die zugehörige MD5-Datei geprüft werden:

```bash
wget --output-document schleswig-holstein-latest.osm.pbf.md5 \
  https://download.geofabrik.de/europe/germany/schleswig-holstein-latest.osm.pbf.md5

md5sum --check schleswig-holstein-latest.osm.pbf.md5
```

## 5. Flensburg ausschneiden

Für Stadtplaner genügt ein gepufferter Ausschnitt um Flensburg. Die Bounding Box ist als `West,Süd,Ost,Nord` angegeben:

```bash
osmium extract \
  --bbox 9.30,54.70,9.60,54.90 \
  --strategy smart \
  --overwrite \
  --output flensburg.osm.pbf \
  schleswig-holstein-latest.osm.pbf
```

Die großzügige Box verhindert, dass Gebäude oder Multipolygon-Relationen am Stadtrand unnötig abgeschnitten werden. Inhalt prüfen:

```bash
osmium fileinfo --extended flensburg.osm.pbf
osmium check-refs flensburg.osm.pbf
```

## 6. In osm2pgsql-Stagingtabellen importieren

Der Import erfolgt zunächst in getrennte Tabellen. Dadurch bleibt der bisherige produktive Inhalt von `osm_features` während Download und Verarbeitung verfügbar.

```bash
osm2pgsql \
  --create \
  --slim \
  --drop \
  --latlong \
  --hstore-all \
  --prefix osm_stage \
  --database open_city_map \
  --host localhost \
  --user oklab \
  flensburg.osm.pbf
```

Wichtige Optionen:

- `--latlong` speichert Geometrien in EPSG:4326, passend zu Stadtplaner.
- `--hstore-all` erhält alle OSM-Tags in der Spalte `tags`.
- `--prefix osm_stage` trennt Import- und Anwendungstabellen.
- `--drop` entfernt osm2pgsql-Middletables nach dem Vollimport. Dieser Ablauf verwendet bewusst regelmäßige Vollimporte statt Minutely-Diffs.

`osm2pgsql` 2.1 akzeptiert hierfür `--user` beziehungsweise `-U`; `--username` ist keine gültige osm2pgsql-Option. Wird `--user` weggelassen, verwendet libpq je nach Umgebung beispielsweise `PGUSER`, `.pgpass` oder den Namen des Betriebssystembenutzers. Deshalb sollte die Rolle auf Servern explizit angegeben werden.

Ergebnis prüfen:

```bash
psql --host localhost --username oklab --dbname open_city_map \
  --command '\d+ public.osm_stage_point'

psql --host localhost --username oklab --dbname open_city_map \
  --command '\d+ public.osm_stage_polygon'
```

## 7. Stadtplaner-Tabelle atomar aktualisieren

Die Anwendung benötigt nur POIs und Flächen mit fachlich relevanten Tags. Punkte und Polygone werden innerhalb einer Transaktion ausgetauscht. API-Anfragen sehen daher entweder den alten oder den vollständig neuen Datenstand.

```bash
psql --host localhost --username oklab --dbname open_city_map <<'SQL'
BEGIN;

TRUNCATE TABLE public.osm_features;

INSERT INTO public.osm_features (
    osm_type,
    osm_id,
    geometry,
    tags,
    imported_at
)
SELECT
    'node',
    osm_id,
    ST_Force2D(way),
    COALESCE(tags - 'way_area'::text, ''::hstore)::jsonb,
    now()
FROM public.osm_stage_point
WHERE tags ?| ARRAY[
    'name', 'shop', 'amenity', 'office', 'craft',
    'tourism', 'leisure', 'building'
];

INSERT INTO public.osm_features (
    osm_type,
    osm_id,
    geometry,
    tags,
    imported_at
)
SELECT
    CASE WHEN osm_id < 0 THEN 'relation' ELSE 'way' END,
    abs(osm_id),
    ST_Force2D(ST_UnaryUnion(ST_Collect(way))),
    COALESCE((array_agg(tags - 'way_area'::text))[1], ''::hstore)::jsonb,
    now()
FROM public.osm_stage_polygon
WHERE tags ?| ARRAY[
    'name', 'shop', 'amenity', 'office', 'craft',
    'tourism', 'leisure', 'building'
]
GROUP BY osm_id
ON CONFLICT (osm_type, osm_id) DO UPDATE
SET geometry = EXCLUDED.geometry,
    tags = EXCLUDED.tags,
    imported_at = EXCLUDED.imported_at;

COMMIT;

ANALYZE public.osm_features;
SQL
```

Bei einem SQL-Fehler wird die Transaktion nicht committed. Der vorherige Bestand bleibt dann erhalten.

## 8. Import verifizieren

Anzahl und Geometrietypen prüfen:

```bash
psql --host localhost --username oklab --dbname open_city_map <<'SQL'
SELECT osm_type, GeometryType(geometry), count(*)
FROM public.osm_features
GROUP BY osm_type, GeometryType(geometry)
ORDER BY osm_type, GeometryType(geometry);

SELECT min(imported_at), max(imported_at), count(*)
FROM public.osm_features;
SQL
```

SRID und Indizes prüfen:

```bash
psql --host localhost --username oklab --dbname open_city_map <<'SQL'
SELECT ST_SRID(geometry), count(*)
FROM public.osm_features
GROUP BY ST_SRID(geometry);

SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'osm_features'
ORDER BY indexname;
SQL
```

Erwartet werden ausschließlich SRID `4326` sowie unter anderem:

```text
idx_osm_features_geometry  USING gist
idx_osm_features_tags      USING gin
```

## 9. Stadtplaner auf lokale Daten umstellen

In `backend/.env` den externen Fallback deaktivieren:

```dotenv
OSM_EXTERNAL_FALLBACK_ENABLED=false
OVERPASS_API_URL=
```

Danach das Backend neu starten. Der Neustart leert zugleich den prozesslokalen OSM-Cache:

```bash
sudo systemctl restart stadtplaner-api
sudo systemctl status stadtplaner-api --no-pager
```

Falls das Backend nicht über systemd läuft, den tatsächlich verwendeten Uvicorn-/Container-Prozess neu starten.

## 10. API testen

Lokal:

```bash
curl --fail-with-body \
  http://localhost:8000/api/v1/polygons/by-slug/nahrungsmittel-drogerie-2/osm
```

Produktion:

```bash
curl --fail-with-body \
  https://api.stadtplaner.oklabflensburg.de/api/v1/polygons/by-slug/nahrungsmittel-drogerie-2/osm
```

Eine erfolgreiche lokale Antwort enthält:

```json
{
  "source": "local",
  "matches": [],
  "primary_match": null
}
```

`matches` ist gefüllt, wenn passende importierte OSM-Objekte das Stadtplaner-Polygon räumlich treffen. `source: "none"` bedeutet, dass die lokale Tabelle erreichbar ist, aber keine passenden Objekte gefunden wurden.

## 11. Regelmäßige Aktualisierung

Für eine kleine regionale Datenmenge ist ein täglicher oder wöchentlicher Vollimport der einfachste robuste Betrieb:

1. neue Schleswig-Holstein-PBF-Datei herunterladen;
2. neuen Flensburg-Extrakt erstellen;
3. `osm_stage_*` mit `osm2pgsql --create` neu aufbauen;
4. `osm_features` innerhalb einer Transaktion aktualisieren;
5. Abfragen und Logs prüfen;
6. Backend neu starten oder den Cache auslaufen lassen.

Für häufigere Aktualisierungen können später osm2pgsql-Slim-Tabellen und OSM-Diffs verwendet werden. Dann darf beim Erstimport `--drop` nicht gesetzt werden. Für den aktuellen Stadtplaner-Betrieb ist der dokumentierte Vollimport leichter zu überwachen und wiederherzustellen.

## 12. Fehlerbehebung

### `permission denied for table osm_features`

Migration und Import laufen mit verschiedenen PostgreSQL-Rollen. Die gezielten Rechte aus Abschnitt 2 vergeben oder beide Prozesse mit derselben kontrollierten Rolle ausführen.

### `relation hstore does not exist`

Die Erweiterung fehlt:

```bash
sudo -u postgres psql --dbname open_city_map \
  --command 'CREATE EXTENSION IF NOT EXISTS hstore;'
```

### API liefert `source: "none"`

Prüfen:

```bash
psql --host localhost --username oklab --dbname open_city_map \
  --command 'SELECT count(*) FROM public.osm_features;'
```

Ist die Tabelle gefüllt, sollte anschließend geprüft werden, ob das betreffende Polygon innerhalb des Flensburg-Extrakts liegt und ob dort relevante OSM-Tags vorhanden sind.

### API liefert weiterhin `source: "overpass"`

Entweder läuft noch ein Backend-Prozess mit alter `.env`, oder der alte Cache ist noch aktiv. Alle Backend-Prozesse mit der aktualisierten Konfiguration neu starten und kontrollieren, dass `OSM_EXTERNAL_FALLBACK_ENABLED=false` geladen wird.

### Import benötigt zu viel Platz

Die PBF-Datei zuerst wie beschrieben mit Osmium verkleinern. Nach erfolgreicher Übernahme können nicht mehr benötigte Stagingtabellen entfernt werden; für den nächsten Vollimport legt osm2pgsql sie erneut an:

```sql
DROP TABLE IF EXISTS public.osm_stage_point;
DROP TABLE IF EXISTS public.osm_stage_line;
DROP TABLE IF EXISTS public.osm_stage_polygon;
DROP TABLE IF EXISTS public.osm_stage_roads;
```

Vor dem Löschen immer sicherstellen, dass `osm_features` erfolgreich gefüllt und geprüft wurde.

## Weiterführende Dokumentation

- [Interner OSM-Datenvertrag](docs/osm-data.md)
- [Geofabrik Schleswig-Holstein](https://download.geofabrik.de/europe/germany/schleswig-holstein.html)
- [osm2pgsql-Handbuch](https://osm2pgsql.org/doc/manual.html)
- [Osmium Extract](https://docs.osmcode.org/osmium/latest/osmium-extract.html)
