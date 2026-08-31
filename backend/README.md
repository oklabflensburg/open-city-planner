# Stadtplaner Backend

Das FastAPI-Backend stellt öffentliche GIS-, Polygon-, OSM-, Analytics- und Analysis-Area-Ressourcen bereit. PostgreSQL mit PostGIS ist die fachliche Datenbank; Redis cached ausschließlich wiederberechenbare Leseantworten.

## Entwicklung

```bash
cp .env.example .env
python3 -m pip install 'uv==0.12.5'
uv sync --frozen --extra dev
uv run python -m app.cli.module_migrations upgrade
uv run uvicorn app.main:app --reload
```

Mindestens `DATABASE_URL`, eine sichere `JWT_SECRET_KEY` und die erlaubten `CORS_ORIGINS` konfigurieren. Redis ist in der lokalen Entwicklung bei `REDIS_REQUIRED=false` optional. Die vollständige Variablenliste steht in `.env.example`; produktive Installation, persistente Secrets und Service-Konfiguration sind zentral in [Deployment und Betrieb](../docs/deployment.md) sowie der [Produktions-Sicherheitscheckliste](../docs/security/production-checklist.md) dokumentiert.

## Analysegebiete

Die Analysis-Areas-Domäne, ihre öffentlichen `/api/v1/analysis-areas/**`-Routen
und ihre historische Migrationsquelle gehören ausschließlich zum installierbaren
Modul [`ocp-module-analysis-areas`](https://github.com/oklabflensburg/ocp-module-analysis-areas).
Der Host stellt dafür nur Module Runtime, öffentliche SDK-Ports und dokumentierte
Nachbarverträge bereit. Ohne aktiviertes Modul gibt es keine Gebiets-Runtime und
keinen Built-in-Fallback. Installation und Cutover stehen in
[Analysis Areas als Produktionsmodul](../docs/modules/analysis-areas-module.md).

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
uv run pytest
uv run ruff check app tests
```

Der gemeinsame Host-/Modulgraph wird mit `uv run python -m app.cli.module_migrations preflight`
geprüft und mit `uv run python -m app.cli.module_migrations upgrade` eingespielt.
Cache-Versionen werden nach Polygonänderungen, Kennzahlenpflege und OSM-Import
durch die jeweiligen Owner erhöht.

Produktionsdeployment, Worker und Timer gehören nicht in diesen Entwicklungs-Quickstart. Dafür gilt [docs/deployment.md](../docs/deployment.md).
