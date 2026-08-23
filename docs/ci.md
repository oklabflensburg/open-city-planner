# Continuous Integration

Die CI ist in fünf getrennte GitHub-Actions-Workflows gegliedert. Alle Workflows
lassen sich manuell starten. Backend, Frontend und E2E laufen zusätzlich bei jedem
Push und Pull Request, ohne Pfadfilter. Dadurch verschwinden Required Checks auch
bei reinen Dokumentationsänderungen nicht.

## Workflows und Checks

| Workflow | Stabiler Jobname | Prüfung |
| --- | --- | --- |
| Backend CI | `backend-lint` | Ruff sowie Import- und Startkonfigurations-Smoke-Test |
| Backend CI | `backend-tests` | vollständige Pytest-Suite |
| Backend CI | `backend-migrations` | genau ein Alembic-Head und Upgrade einer frischen PostGIS-Datenbank |
| Frontend CI | `frontend-tests` | vollständige Vitest-Suite |
| Frontend CI | `frontend-typecheck` | Nuxt-/Vue-Typecheck |
| Frontend CI | `frontend-build` | produktiver Nuxt-Build |
| Frontend CI | `frontend-language-audit` | Audit der sichtbaren Sprache |
| E2E Tests | `e2e` | vollständige Playwright-Suite mit echtem Frontend, Backend und frischer PostGIS-Datenbank |
| Supply Chain | `verify` | Lockfile-Konsistenz, SHA-/Digest-Pins und negative Policy-Regressionstests |
| Supply Chain | `sbom` | transitive CycloneDX-SBOMs für Backend und Frontend |

Die Workflows verwenden exakt Python 3.12.14 aus `.python-version`, Node.js 22.23.2
aus `.node-version`, uv 0.12.5 und die in `frontend/package.json` festgelegte
pnpm-Version 11.22.0. Backend-Abhängigkeiten stammen ausschließlich aus
`backend/uv.lock`; Frontend-Abhängigkeiten werden ausschließlich mit
`--frozen-lockfile` installiert. Redis wird nicht gestartet, weil die Tests den optionalen
Cache nicht benötigen. Netzwerkzugriffe zu Mastodon, OSM, Wikidata, Wikipedia,
Nominatim oder Superset sind in der E2E-Umgebung deaktiviert beziehungsweise in
den betroffenen Tests gemockt.

Playwright installiert sein eigenes Chromium. Fehlgeschlagene Läufe laden Traces,
Screenshots und den HTML-Bericht für sieben Tage als Artefakt hoch. Retries bleiben
auf `0`, damit instabile Tests sichtbar werden. Der CI-Lauf verwendet einen Worker,
weil mehrere Tests denselben Nuxt-Entwicklungsserver verwenden und parallele
Reloads dessen Hydration und gemockte Browseranfragen gegenseitig beeinflussen.
Die Testdaten erzeugt
`backend/tests/e2e_seed.py` nach dem vollständigen Alembic-Upgrade ausschließlich
für die frische CI-Datenbank.

## Lokale Prüfung

Backend:

```bash
cd backend
python3 -m pip install 'uv==0.12.5'
uv lock --check
uv sync --frozen --extra dev --no-editable
uv run ruff check app tests
uv run pytest
uv run python -c "from app.main import app; assert app.title"
uv run alembic heads
uv run alembic upgrade head
```

Frontend:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm test
pnpm typecheck
pnpm build
pnpm audit:language
```

E2E benötigt eine leere PostGIS-Datenbank. `DATABASE_URL` muss auf diese
Testdatenbank zeigen:

```bash
cd backend
uv sync --frozen --extra dev --no-editable
uv run alembic upgrade head
uv run python tests/e2e_seed.py
cd ../frontend
pnpm exec playwright install chromium
pnpm test:e2e
```

Produktivdatenbanken dürfen niemals als E2E-Ziel verwendet werden. Der Seed ist
für eine frische, isolierte Datenbank vorgesehen.

`alembic check` ist derzeit absichtlich kein CI-Schritt. Die Autogenerierung
behandelt Tabellen der von PostGIS installierten Tiger-/Topology-Schemata sowie
einzelne bestehende, nicht in der Alembic-Metadatenmenge registrierte Objekte als
zu entfernende Anwendungstabellen. Das erzeugt auf einer korrekt migrierten,
frischen Datenbank Fehlalarme. Bis die Alembic-Filter und die Metadatenregistrierung
bereinigt sind, prüft CI deshalb den eindeutigen Head und das vollständige Upgrade.

## Security-Workflow

Bei Pull Requests prüft GitHubs Dependency Review neu hinzugekommene
Abhängigkeiten. Das netzabhängige `pnpm audit` läuft wöchentlich montagmorgens und
bei manuellem Start. Es ist bewusst kein Required Check: Änderungen oder Ausfälle
externer Advisory-Datenbanken sollen reproduzierbare Pull-Request-Prüfungen nicht
zufällig blockieren, bleiben im eigenen Workflow aber sichtbar und fehlschlagend.

Dependabot aktualisiert GitHub Actions, `backend/uv.lock` und
`frontend/pnpm-lock.yaml` ausschließlich per Pull Request. Jeder dieser Pull
Requests durchläuft das vollständige Release Gate. Weitere Details stehen in
[supply-chain.md](supply-chain.md).

## Empfohlene Branch Protection für `main`

Aktiviere „Require status checks to pass before merging“ und wähle diese stabilen
Checks aus:

- `backend-lint`
- `backend-tests`
- `backend-migrations`
- `frontend-tests`
- `frontend-typecheck`
- `frontend-build`
- `frontend-language-audit`
- `e2e`
- `verify`
- `sbom`
- `gate`

Zusätzlich empfehlen sich mindestens eine Freigabe, „Require conversation
resolution before merging“ und „Require branches to be up to date before merging“.
Der geplante Security-Audit bleibt beobachtbar, aber absichtlich außerhalb der
Required Checks.
