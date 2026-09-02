# Stadtplaner Backend

Das FastAPI-Backend stellt Authentifizierung, Administration, Notifications sowie
generische GIS-, Polygon- und OSM-Plattformverträge bereit. Installierte Module
ergänzen Fach-APIs, Jobs und Contributions. PostgreSQL mit PostGIS ist die
persistente Datenbank; Redis cached ausschließlich wiederberechenbare Leseantworten.

## Entwicklung

```bash
cp .env.example .env
python3 -m pip install 'uv==0.12.5'
uv sync --frozen --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Mindestens `DATABASE_URL`, eine sichere `JWT_SECRET_KEY` und die erlaubten `CORS_ORIGINS` konfigurieren. Redis ist in der lokalen Entwicklung bei `REDIS_REQUIRED=false` optional. Die vollständige Variablenliste steht in `.env.example`; produktive Installation, persistente Secrets und Service-Konfiguration sind zentral in [Deployment und Betrieb](../docs/deployment.md) sowie der [Produktions-Sicherheitscheckliste](../docs/security/production-checklist.md) dokumentiert.

## Polygone, OSM und Fachmodule

Der Host verwaltet generische Nutzerpolygone und lokale OSM-Snapshots. Neutrale
Query-, Identity-, Spatial-Match- und Polygon-Metrik-Ports machen diese Daten für
Module nutzbar, ohne deren Fachmodelle in den Host zu übernehmen. Import und
Provenienz sind in [osm-data.md](../docs/osm-data.md) beschrieben.

Analysegebiete, Statistik, Suche, Vergleich, Assistant, fachliche Analytics,
Social Publishing und Wikidata-Anreicherung sind keine Host-Runtime. Ohne ein
entsprechendes installiertes Modul fehlen ihre Routes und UI-Contributions
absichtlich; es gibt keinen Built-in-Fallback. Der Modulbetrieb ist unter
[Modulbetrieb](../docs/modules/operations.md) dokumentiert.

## Administratives Auditlog

`GET /api/v1/admin/audit-logs` liefert das bestehende `admin_audit_logs`-Auditlog ausschließlich an Benutzer mit `is_superuser = true`. Der read-only Endpoint ist auf 100 Einträge pro Seite begrenzt, sortiert neueste Ereignisse zuerst und unterstützt Aktions-, Akteur-, Ressourcen-, Zeitraum- und Textfilter. Die Ausgabe verwendet ein explizites DTO und bereinigt beliebige Metadaten rekursiv um Passwörter, Tokens und andere Authentifizierungsgeheimnisse. Die Rolle `VERWALTUNG` allein gewährt keinen Zugriff; Antworten dürfen nicht gecacht werden.

Die Tabelle speichert derzeit Akteur, Zielbenutzer, Aktion, optionale Rolle und Zeitpunkt. IP-Adresse, User-Agent sowie allgemeine JSON-Metadaten werden nicht erhoben. Der vorhandene Index auf `created_at` bedient die Standardabfrage `ORDER BY created_at DESC LIMIT ...`; deshalb ist keine zusätzliche Migration erforderlich.

## API-Dokumentation und Tests

- Swagger UI: `/docs`
- ReDoc: `/redoc`
- OpenAPI: `/openapi.json`

```bash
uv run pytest
uv run ruff check app tests
```

Migrationen werden mit `uv run alembic upgrade head` eingespielt. Cache-Versionen
werden nach generischen Polygon- und OSM-Änderungen durch die zuständigen Services
erhöht; Module besitzen ihre fachliche Invalidierung.

Produktionsdeployment, Worker und Timer gehören nicht in diesen Entwicklungs-Quickstart. Dafür gilt [docs/deployment.md](../docs/deployment.md).
