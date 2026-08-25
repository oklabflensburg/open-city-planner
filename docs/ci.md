# Continuous Integration

Die CI ist in getrennte GitHub-Actions-Workflows gegliedert. Alle Workflows
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
| Frontend CI | `frontend-build` | produktiver Nuxt-Build und zentraler SSR-/SEO-Audit über Sitemap-, Noindex-, Redirect- und Fehler-Routen |
| Frontend CI | `frontend-language-audit` | Audit der sichtbaren Sprache |
| E2E Tests | `e2e` | vollständige Playwright-Suite mit echtem Frontend, Backend und frischer PostGIS-Datenbank |
| Security | `security-policy-validation` | Format, Vollständigkeit und Ablauf befristeter Security-Ausnahmen sowie negative Policy-Tests |
| Security | `backend-audit` | `pip-audit 2.10.1` gegen den eingefrorenen Python-Produktionssatz |
| Security | `frontend-audit` | `pnpm audit --prod` gegen das eingefrorene Frontend-Lockfile |
| Security | `sast` | CodeQL-SAST für Python und JavaScript/TypeScript mit SARIF-Upload und High/Critical-Gate |
| Security | `secret-scan` | Gitleaks gegen die vollständige Historie mit redigierter Ausgabe und SARIF-Upload |
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
pnpm audit:seo
```

`pnpm audit:seo` startet den zuvor erzeugten Nitro-Production-Server und eine
lokale Fixture-API auf freien Loopback-Ports. SSR-Aufrufe verwenden dabei die
private `NUXT_API_INTERNAL_BASE_URL`; alle geprüften Canonical-, OpenGraph-,
Twitter-, Sitemap- und JSON-LD-URLs verwenden weiterhin ausschließlich die
production-artigen öffentlichen HTTPS-Origins. Der Audit crawlt alle
Sitemap-Ziele sowie eine kompakte Matrix aus Noindex-, Auth-, Admin-,
Social-Preview-, Redirect- und 404-Routen. Zusätzlich prüft er das globale
Favicon-/Manifest-Set, die tatsächlichen PNG-Abmessungen und den 1200×630-
Social-Image-Fallback aller indexierbaren Seiten.

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

Der Security-Workflow läuft vollständig bei Pull Requests, Pushes, manuellen
Starts, montags um 04:23 UTC und bei jedem Aufruf durch das Release Gate.
Backend- und Frontend-Audit, beide CodeQL-Sprachen, Secret Scan und
Policy-Validierung laufen dabei immer. Dependency Review ist bewusst das
zusätzliche PR-Diff-Gate; vollständige Audits übernehmen Push und Schedule.

Alle Security-Jobs sind über den reusable Workflow Teil des verpflichtenden
Release Gate. High/Critical-Funde blockieren, ebenso ungültige oder abgelaufene
Ausnahmen. `pip-audit` blockiert vorsorglich alle bekannten Advisories, weil
dessen Quellen nicht für jeden Fund einen vergleichbaren Schweregrad liefern.
Die genaue Severity-, SLA- und Ausnahme-Policy steht in [SECURITY.md](../SECURITY.md).

CodeQL und Gitleaks laden SARIF nach GitHub Security / Code Scanning hoch. Nur
diese Jobs erhalten `security-events: write`; ansonsten gilt `contents: read`.
CodeQL erhält zusätzlich `packages: read` für das offizielle Bundle. Es gibt
kein `pull_request_target`, keine Produktions-Secrets und kein `write-all`.

Lokale Security-Prüfung:

```bash
cd backend
python3 -m pip install 'uv==0.12.5'
uv sync --frozen --extra security --no-editable
uv run --frozen --extra security python ../scripts/security/audit_backend.py
uv run --frozen --extra security python ../scripts/security/validate_security_exceptions.py
cd ..
backend/.venv/bin/python -m unittest scripts.security.tests.test_security_gates

cd frontend
pnpm install --frozen-lockfile
../backend/.venv/bin/python ../scripts/security/audit_frontend.py
```

Gitleaks wird in CI über `scripts/security/install_gitleaks.sh` als Version
8.30.1 mit geprüftem SHA-256 installiert. Anschließend:

```bash
scripts/security/install_gitleaks.sh /tmp/ocm-gitleaks
PATH="/tmp/ocm-gitleaks:${PATH}" scripts/security/test_gitleaks_gate.sh
PATH="/tmp/ocm-gitleaks:${PATH}" gitleaks git --redact=100 --config .gitleaks.toml .
```

Die negative Backend-Dependency-Fixture wird von
`scripts/security/test_backend_audit_gate.py` ausschließlich in einem
temporären Verzeichnis erzeugt und niemals installiert oder als
Produktionsmanifest eingecheckt. Sie beweist, dass `pip-audit` non-zero
liefert. Der SARIF-Policy-Test beweist dasselbe für einen künstlichen
High-CodeQL-Fund, der Gitleaks-Test für ein zusammengesetztes synthetisches
Secret.

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
- `security-policy-validation`
- `backend-audit`
- `frontend-audit`
- `sast`
- `secret-scan`
- `verify`
- `sbom`
- `gate`

Zusätzlich empfehlen sich mindestens eine Freigabe, „Require conversation
resolution before merging“ und „Require branches to be up to date before merging“.
Der zusammenfassende `gate`-Job verlangt den erfolgreichen reusable
Security-Workflow und blockiert dadurch auch Production Deployments.
