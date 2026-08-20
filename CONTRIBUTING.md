# Zum Stadtplaner beitragen

Vielen Dank für dein Interesse am Stadtplaner des OK Lab Flensburg. Beiträge zu Code, Dokumentation, Barrierefreiheit, Tests und Datenqualität sind willkommen. Dieses Dokument beschreibt den üblichen Weg von einer Idee bis zu einem prüfbaren Pull Request.

## Vor dem Start

- Prüfe zuerst die [vorhandenen Issues](https://github.com/oklabflensburg/open-city-planner/issues), damit Arbeit nicht doppelt entsteht.
- Für Fehlerberichte sind Schritte zum Reproduzieren, erwartetes und tatsächliches Verhalten, Browser beziehungsweise Betriebssystem und – falls sinnvoll – ein anonymisierter Screenshot hilfreich.
- Besprich größere Funktions-, Datenmodell- oder Architekturänderungen vor der Umsetzung in einem Issue.
- Veröffentliche keine Zugangsdaten, personenbezogenen Daten oder nicht öffentlichen Verwaltungsdaten.

Sicherheitslücken gehören nicht in ein öffentliches Issue. Melde sie vertraulich über die [Kontaktseite des Stadtplaners](https://stadtplaner.oklabflensburg.de/kontakt) und beschreibe zunächst nur die nötigen technischen Eckpunkte.

## Entwicklungsumgebung

Benötigt werden:

- Node.js mit `pnpm` 11
- Python 3.12 oder neuer
- PostgreSQL mit PostGIS
- optional Redis für den gemeinsam genutzten Read-Cache

Frontend einrichten:

```bash
cd frontend
cp .env.example .env
pnpm install
pnpm dev
```

Backend einrichten:

```bash
cd backend
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Die lokalen Standardadressen stehen im [README](README.md); alle Variablen sind in den jeweiligen `.env.example`-Dateien beschrieben. Echte Secrets gehören ausschließlich in die nicht versionierte `.env`-Datei. Maintainer finden den produktiven Ablauf in [docs/deployment.md](docs/deployment.md).

## Änderungen umsetzen

1. Forke das Repository und erstelle einen kurzen, thematisch klaren Branch.
2. Halte den Umfang fokussiert. Vermische Fehlerbehebung, Refactoring und neue Funktion nur, wenn sie technisch untrennbar sind.
3. Ergänze oder aktualisiere Tests für geändertes Verhalten.
4. Passe Benutzer- oder Betriebsdokumentation an, wenn sich Bedienung, API, Datenmodell oder Konfiguration ändern.
5. Führe die relevanten Prüfungen lokal aus und eröffne anschließend einen Pull Request gegen `main`.

### Frontend

- Nutze Vue 3 und Nuxt mit TypeScript sowie die vorhandenen Komponenten und Design-Tokens.
- Achte auf semantisches HTML, Tastaturbedienung, sichtbaren Fokus, ausreichenden Kontrast und verständliche deutsche Beschriftungen.
- Öffentliche Seiten müssen mit SSR funktionieren. Browser-only Bibliotheken wie MapLibre dürfen den serverseitigen Build nicht beeinträchtigen.
- Pflege projektweite Werte in einer zentralen Konfiguration statt als wiederholte Literale.
- Verwende Lucide-Icons aus dem bestehenden Icon-System und kennzeichne rein dekorative Icons mit `aria-hidden="true"`.

Frontend prüfen:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm test
pnpm typecheck
pnpm build
pnpm audit:language
```

Für Änderungen an wichtigen Nutzerwegen zusätzlich:

```bash
cd frontend
pnpm exec playwright install chromium
pnpm test:e2e
```

Die E2E-Suite startet Backend und Frontend selbst. Aktiviere vorher die Backend-
Umgebung oder setze `PLAYWRIGHT_BACKEND_PYTHON` auf den gewünschten Python-
Interpreter. Ein vorhandenes `backend/.venv` wird automatisch erkannt. Nur für
einen bewusst verwendeten Systembrowser kann optional
`PLAYWRIGHT_CHROMIUM_PATH` gesetzt werden; standardmäßig nutzt Playwright sein
eigenes Chromium.

### Backend und Datenbank

- Halte öffentliche, authentifizierte und Verwaltungsdaten konsequent getrennt.
- Erzwinge Berechtigungen, Validierung und Datenschutz serverseitig; eine ausgeblendete Schaltfläche ist keine Zugriffskontrolle.
- GeoJSON-Eingaben verwenden EPSG:4326 mit der Reihenfolge Längengrad/Breitengrad. Räumliche Berechnungen müssen das dafür vorgesehene metrische Koordinatensystem nutzen.
- Erzeuge für Schemaänderungen eine Alembic-Migration. Ändere keine bereits veröffentlichte Migration nachträglich.
- Bewahre Abwärtskompatibilität öffentlicher API-Antworten, sofern eine Änderung nicht vorher abgestimmt wurde.

Backend prüfen:

```bash
cd backend
source .venv/bin/activate
ruff check app tests
pytest
python -c "from app.main import app; assert app.title"
```

Eine neue Migration lässt sich im Backend beispielsweise so erzeugen und prüfen:

```bash
alembic revision --autogenerate -m "kurze beschreibung"
alembic heads
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Prüfe die automatisch erzeugte Migration immer manuell, besonders bei PostGIS-Typen, Constraints und Datenmigrationen.

Eine vollständige Übersicht der CI-Jobs und der als Required Checks empfohlenen
Job-Namen steht in [docs/ci.md](docs/ci.md).

## Pull Requests

Ein guter Pull Request enthält:

- eine kurze Beschreibung von Problem und Lösung,
- einen Verweis auf das zugehörige Issue, falls vorhanden,
- die ausgeführten Tests und deren Ergebnis,
- Screenshots oder kurze Aufnahmen bei sichtbaren UI-Änderungen, möglichst für Desktop und Mobilgerät,
- Hinweise zu Migration, Konfiguration, Rollout oder Rückwärtskompatibilität,
- ausschließlich für den Beitrag notwendige Dateien.

Pull Requests müssen nicht groß sein. Kleine, nachvollziehbare Änderungen lassen sich meist schneller und sicherer prüfen. Review-Hinweise sind Teil der Zusammenarbeit; offene Punkte sollten im Pull Request geklärt werden, bevor er zusammengeführt wird.

## Dokumentation und Sprache

Benutzeroberfläche und öffentliche Projektdokumentation sind überwiegend deutsch. Codebezeichner und technische Kommentare können englisch sein. Formuliere Texte verständlich, konkret und inklusiv und erfinde keine Funktionen, Zuständigkeiten oder Datenquellen.

Für eine neue sichtbare Kernfunktion prüfe zusätzlich den öffentlichen Eintrag in `frontend/app/config/documentation.ts`, passende Suchbegriffe, technische Dokumentation und die Dokumentationstests. Der technische Einstieg steht in [docs/README.md](docs/README.md); Deployment bleibt eine Maintainer-Aufgabe und wird nicht im Contributor-Ablauf dupliziert.

Mit deinem Beitrag bestätigst du, dass du die eingereichten Änderungen selbst erstellt hast oder zu ihrer Weitergabe berechtigt bist.
