# Stadtplaner Backend

Das FastAPI-Backend stellt öffentliche GIS-, Polygon-, OSM-, Analytics- und Analysis-Area-Ressourcen bereit. PostgreSQL mit PostGIS ist die fachliche Datenbank; Redis cached ausschließlich wiederberechenbare Leseantworten.

## Entwicklung

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Mindestens `DATABASE_URL`, eine sichere `JWT_SECRET_KEY` und die erlaubten `CORS_ORIGINS` konfigurieren. Redis ist bei `REDIS_REQUIRED=false` optional. Das vollständige Environment-Beispiel und der PostgreSQL-/PostGIS-Aufbau stehen im Root-[README](../README.md) und in [SETUP.md](../SETUP.md).

`JWT_SECRET_KEY` signiert Access- und Refresh-JWTs und muss bei Deployments, Restarts
und über alle Uvicorn-/Gunicorn-Worker hinweg identisch bleiben. Einen Wert einmalig
mit `python -c "import secrets; print(secrets.token_urlsafe(64))"` erzeugen und nur in
der persistenten serverseitigen `backend/.env` beziehungsweise dem systemd-
`EnvironmentFile` speichern. Ein normaler Deployment-Schritt darf diesen Wert nicht
neu erzeugen. In Produktion verweigert das Backend den Start bei fehlendem,
bekanntem Entwicklungs- oder zu kurzem Schlüssel.

Ein systemd-Service muss dieselbe Datei bei jedem Worker und Neustart laden, zum
Beispiel:

```ini
[Service]
WorkingDirectory=/opt/stadtplaner/backend
EnvironmentFile=/opt/stadtplaner/backend/.env
ExecStart=/opt/stadtplaner/backend/.venv/bin/uvicorn app.main:app --workers 4
```

Die `.env` muss außerhalb des Deployment-Austauschs erhalten bleiben und darf nur
für den Service-Benutzer lesbar sein. Eine bewusste Änderung von `JWT_SECRET_KEY`
ist eine Schlüsselrotation und invalidiert ohne Key-Ring bestehende Access- und
Refresh-JWTs; ein gewöhnlicher Restart oder Deployment darf daher keine neue Datei
beziehungsweise keinen neuen Schlüssel erzeugen.

## Analysegebiete und OSM

`analysis_areas` enthält die Typen `MUNICIPALITY`, `DISTRICT` und `QUARTER`, global eindeutige stabile Slugs, Parent-Relationen, MultiPolygon-Geometrien, Zentroid und OSM-Provenienz. Der Boundary-Sync verwendet lokale OSM-Daten, bestimmt räumliche Parents und ordnet Stadtplaner-Flächen über `ST_PointOnSurface` zu. Ausführung und Importvorbereitung sind in [osm-data.md](../docs/osm-data.md) beschrieben.

Der Area-Sync übernimmt außerdem die OSM-Tags `wikidata` und `wikipedia`. Anschließend löst `WikidataEnrichmentService` bevorzugt die explizite Q-ID, danach einen deutschen Wikipedia-Titel und zuletzt konservativ Name, Parent und Referenzpunkt über die offizielle Wikibase API auf. Ergebnisse, Prüffrist und Matchzustand werden persistent gespeichert; öffentliche Requests fragen Wikimedia nie live ab. `python -m app.cli.sync_wikidata [--force]` startet nur die Anreicherung, `sync_analysis_areas` führt sie standardmäßig nach dem OSM-Import aus (`--skip-wikidata` deaktiviert sie). Manuell verifizierte Matches werden nicht überschrieben; abweichende OSM-IDs erzeugen `CONFLICT`.

Öffentliche Gebiets-Endpunkte liegen unter `/api/v1/analysis-areas`; Detail, Analytics, Gesamtstadtvergleich und eine begrenzte Flächenliste können über `by-slug/{slug}` geladen werden. Eigentümer-, Preis- und interne Verwaltungsfelder sind nicht Teil dieser DTOs.

## Administratives Auditlog

`GET /api/v1/admin/audit-logs` liefert das bestehende `admin_audit_logs`-Auditlog ausschließlich an Benutzer mit `is_superuser = true`. Der read-only Endpoint ist auf 100 Einträge pro Seite begrenzt, sortiert neueste Ereignisse zuerst und unterstützt Aktions-, Akteur-, Ressourcen-, Zeitraum- und Textfilter. Die Ausgabe verwendet ein explizites DTO und bereinigt beliebige Metadaten rekursiv um Passwörter, Tokens und andere Authentifizierungsgeheimnisse. Die Rolle `VERWALTUNG` allein gewährt keinen Zugriff; Antworten dürfen nicht gecacht werden.

Die Tabelle speichert derzeit Akteur, Zielbenutzer, Aktion, optionale Rolle und Zeitpunkt. IP-Adresse, User-Agent sowie allgemeine JSON-Metadaten werden nicht erhoben. Der vorhandene Index auf `created_at` bedient die Standardabfrage `ORDER BY created_at DESC LIMIT ...`; deshalb ist keine zusätzliche Migration erforderlich.

## Kommunale Statistik

Der strukturierte Import aus dem öffentlichen Flensburger Superset-Zahlenspiegel läuft mit `python -m app.cli.import_flensburg_statistics`. Er verwendet ausschließlich die öffentliche Chart-Data-API, validiert CSV-Schema und Gebietsmapping und speichert normalisierte Datasets, Metriken, Zeitreihen, Importläufe sowie die explizite Zuordnung zu `analysis_areas`. Details, Inventar, Lizenz und Betrieb stehen in [flensburg-statistics.md](../docs/flensburg-statistics.md).

Öffentliche Endpunkte sind `/api/v1/analysis-areas/by-slug/{slug}/statistics`, die zugehörige `/{metric_key}`-Zeitreihe und `/api/v1/data-sources/status`. Webseiten greifen ausschließlich auf PostgreSQL und niemals live auf Superset zu.

## API-Dokumentation und Tests

- Swagger UI: `/docs`
- ReDoc: `/redoc`
- OpenAPI: `/openapi.json`

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check app tests
```

Migrationen werden mit `alembic upgrade head` eingespielt. Cache-Versionen werden nach Area-Sync, Polygonänderungen, Kennzahlenpflege und OSM-Import durch die Services erhöht.
