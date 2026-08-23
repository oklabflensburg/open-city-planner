# Stadtplaner Flensburg

[![Backend CI](https://github.com/oklabflensburg/open-city-planner/actions/workflows/backend.yml/badge.svg)](https://github.com/oklabflensburg/open-city-planner/actions/workflows/backend.yml)
[![Frontend CI](https://github.com/oklabflensburg/open-city-planner/actions/workflows/frontend.yml/badge.svg)](https://github.com/oklabflensburg/open-city-planner/actions/workflows/frontend.yml)
[![E2E Tests](https://github.com/oklabflensburg/open-city-planner/actions/workflows/e2e.yml/badge.svg)](https://github.com/oklabflensburg/open-city-planner/actions/workflows/e2e.yml)
[![Security](https://github.com/oklabflensburg/open-city-planner/actions/workflows/security.yml/badge.svg)](https://github.com/oklabflensburg/open-city-planner/actions/workflows/security.yml)

![Screenshot Stadtplaner Flensburg](https://raw.githubusercontent.com/oklabflensburg/open-city-planner/main/screenshot_stadtplaner.webp)

Der Stadtplaner macht Verkaufsflächen, OpenStreetMap-Informationen, Analysegebiete und ausgewählte kommunale Kennzahlen für Flensburg auf einer interaktiven Karte zugänglich. Öffentliche Inhalte sind ohne Anmeldung lesbar; Bearbeitung und Verwaltung sind serverseitig geschützt.

## Architektur

- `frontend/`: Nuxt 4, Vue 3, Tailwind CSS, MapLibre und Terra Draw;
- `backend/`: FastAPI, SQLAlchemy, GeoAlchemy2 und Alembic;
- PostgreSQL/PostGIS als fachliche Datenbank;
- optionaler Redis-Read-Cache und produktives Backend für gemeinsame Sicherheitszähler;
- lokale OpenStreetMap-Daten, kommunale Statistik und optionale externe Integrationen;
- GitHub Actions für Backend, Frontend, Migrationen, E2E und Security.

## Repository-Struktur

```text
backend/          API, Datenmodelle, Migrationen, CLI und Tests
frontend/         Webanwendung, öffentliches Benutzerhandbuch und E2E-Tests
docs/             technische Entwickler-, Architektur- und Betriebsdokumentation
deploy/ansible/   reproduzierbares Produktionsdeployment
deploy/nginx/     Stadtplaner-spezifische Nginx-Hardening-Vorlagen
deploy/systemd/   mitgelieferte Units für Hintergrundaufgaben
scripts/osm/      initialer OSM-Import und Replikationsupdate
```

## Lokales Schnellsetup

Vorausgesetzt werden Python 3.12 oder neuer, Node.js mit pnpm 11 sowie PostgreSQL mit PostGIS.

Backend:

```bash
cd backend
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend in einem zweiten Terminal:

```bash
cd frontend
cp .env.example .env
pnpm install
pnpm dev
```

Das Frontend läuft standardmäßig auf `http://localhost:3000`, die API auf `http://localhost:8000`. Swagger UI ist unter `http://localhost:8000/docs` erreichbar.

Die lokale Datenbank benötigt die PostGIS-Erweiterung. Alle Werte in den Environment-Beispielen sind vor einem Produktivbetrieb zu prüfen; Entwicklungs-Secrets dürfen nicht übernommen werden.

## Tests

```bash
cd backend
.venv/bin/ruff check app tests
.venv/bin/pytest

cd ../frontend
pnpm test
pnpm typecheck
pnpm build
pnpm audit:language
```

Die E2E-Suite startet Frontend und Backend in einer isolierten Testumgebung:

```bash
cd frontend
pnpm test:e2e
```

Die vollständigen CI-Jobs und stabilen Check-Namen stehen in [docs/ci.md](docs/ci.md).

## Dokumentation

- Das öffentliche Benutzerhandbuch ist in der Anwendung unter `/dokumentation` erreichbar und wird aus `frontend/app/config/documentation.ts` erzeugt.
- [Technische Dokumentation](docs/README.md)
- [Deployment und Betrieb](docs/deployment.md)
- [Ansible-Deployment](deploy/ansible/README.md)
- [Nginx-Hardening und Rate Limits](deploy/nginx/README.md)
- [OpenStreetMap-Daten](docs/osm-data.md)
- [Kommunale Statistik](docs/flensburg-statistics.md)
- [Intelligente Suche](docs/intelligent-search.md) und [Stadtplaner-Assistent](docs/stadtplaner-assistant.md)
- [Produktions-Sicherheitscheckliste](docs/security/production-checklist.md)

## Beiträge und Sicherheit

Hinweise für Issues, lokale Entwicklung und Pull Requests stehen in [CONTRIBUTING.md](CONTRIBUTING.md). Sicherheitslücken bitte nach [SECURITY.md](SECURITY.md) melden und nicht in einem öffentlichen Issue veröffentlichen.

## Lizenz und Datenquellen

Der Quellcode des Stadtplaners steht unter der **GNU Affero General Public License v3.0 (AGPL-3.0-only)**. Die vollständigen Lizenzbedingungen stehen in [LICENSE](LICENSE).

Die AGPL erlaubt Nutzung, Weitergabe und Veränderung des Quellcodes und stellt bei modifizierten, öffentlich über ein Netzwerk bereitgestellten Versionen sicher, dass Nutzerinnen und Nutzer Zugang zum entsprechenden Quellcode erhalten.

OpenStreetMap-Daten bleiben ihrer jeweiligen ODbL-Attribution unterworfen; kommunale Statistik nennt Quelle, Periode und Lizenz am Datensatz. Weitere eingebundene Daten und Abhängigkeiten behalten ihre jeweiligen Lizenzen.
