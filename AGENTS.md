# AGENTS.md

Diese Datei richtet sich an Coding Agents, Automatisierungswerkzeuge und KI-gestützte Entwicklungsassistenten, die Änderungen im Repository `oklabflensburg/open-city-planner` vornehmen. Sie ergänzt `CONTRIBUTING.md`, `SECURITY.md` und die technische Dokumentation. Bei Widersprüchen gelten die spezifischeren Repository-Dokumente und die vorhandene CI als maßgeblich.

## Projektüberblick

Open City Planner ist eine offene Civic-Tech-Web-GIS-Plattform des OK Lab Flensburg.

Technischer Kern:

- Frontend: Nuxt 4, Vue 3, TypeScript, Pinia, Tailwind CSS 4
- Karte: MapLibre GL JS, Terra Draw, Turf
- Backend: FastAPI, SQLAlchemy/GeoAlchemy2, Alembic
- Datenbank: PostgreSQL mit PostGIS
- Cache: Redis optional
- Betrieb: Nginx, systemd, Ansible
- Tests: Vitest, Playwright, Pytest
- Dependency Management: pnpm im Frontend, uv im Backend
- Lizenz des Plattformcodes: AGPL-3.0-only

Das Repository ist produktiv genutzt. Änderungen müssen deshalb nicht nur funktional, sondern auch sicher, testbar, barrierearm, rückwärtskompatibel und deploybar sein.

## Repository-Struktur

- `frontend/` – Nuxt-Anwendung, UI, Stores, Komponenten, SSR und E2E-Tests
- `backend/` – FastAPI-Anwendung, Services, Datenmodelle, Migrationen und Backend-Tests
- `deploy/` – Ansible, Nginx, systemd und Observability-/Betriebskonfiguration
- `docs/` – technische Dokumentation, CI, Deployment, Security und Runbooks
- `scripts/` – Repository-weite Hilfs- und Prüfscripte
- `.github/workflows/` – CI, Security, E2E, Release Gate und Deployment

Bevor du eine Änderung beginnst, lies mindestens die direkt betroffenen Dateien sowie `CONTRIBUTING.md`. Für Security-, CI-, Deployment- oder Betriebsänderungen zusätzlich `SECURITY.md`, `docs/ci.md` und `docs/deployment.md` lesen.

## Arbeitsweise

1. Arbeite von aktuellem `main` aus auf einem kurzen, thematisch klaren Branch.
2. Prüfe vorhandene Issues und Pull Requests, bevor du neue Architektur oder parallele Lösungen einführst.
3. Halte Änderungen fokussiert. Vermische Feature, Refactoring und Infrastruktur nur, wenn sie technisch untrennbar sind.
4. Bevorzuge bestehende Abstraktionen und Komponenten statt neuer paralleler Systeme.
5. Ergänze Tests für jedes geänderte Verhalten und Regressionen.
6. Aktualisiere Dokumentation, wenn sich Bedienung, API, Konfiguration, Datenmodell, Deployment oder Betrieb ändern.
7. Führe die relevanten lokalen Prüfungen aus, bevor ein Pull Request erstellt wird.
8. Deaktiviere keine bestehenden Security-, Test- oder Release-Gates, nur um CI grün zu bekommen.

## Versionen und reproduzierbare Builds

Verwende exakt die im Repository definierten Laufzeit- und Toolversionen:

- Node.js aus `.node-version`
- Python aus `.python-version`
- pnpm aus `frontend/package.json`
- uv gemäß `backend/pyproject.toml`

Frontend-Dependencies ausschließlich mit Lockfile installieren:

```bash
cd frontend
pnpm install --frozen-lockfile
```

Backend-Dependencies über uv und das committed Lockfile installieren:

```bash
cd backend
python -m pip install 'uv==0.12.5'
uv sync --frozen --extra dev
```

Wenn `backend/pyproject.toml` geändert wird, `backend/uv.lock` aktualisieren und anschließend prüfen. Wenn `frontend/package.json` geändert wird, `frontend/pnpm-lock.yaml` konsistent aktualisieren.

Keine beweglichen Toolversionen wie `latest`, unversionierte `pip install`-Aufrufe oder neue frei auflösende Installationspfade in CI/Deployment einführen.

## Frontend-Regeln

- Vue 3 und Nuxt 4 mit TypeScript verwenden.
- Vorhandene UI-Komponenten, Design-Tokens und CSS-Helfer bevorzugen.
- Sichtbare Benutzertexte grundsätzlich auf Deutsch formulieren, sofern kein bestehender i18n-Kontext etwas anderes vorgibt.
- Semantisches HTML, Tastaturbedienung, sichtbaren Fokus, ausreichenden Kontrast und Touch-Targets berücksichtigen.
- Dekorative Icons mit `aria-hidden="true"` markieren.
- Lucide-Icons aus dem bestehenden Icon-System verwenden; keine neue Icon-Library für einzelne Symbole hinzufügen.
- Öffentliche Seiten müssen SSR-fähig bleiben.
- Browser-only Bibliotheken wie MapLibre nur clientseitig verwenden und SSR-Builds nicht brechen.
- Wiederverwendbare Zustände in Stores/Composables zentral halten statt pro Viewport oder Komponente zu duplizieren.
- Responsive GIS-Verhalten für Mobile, Tablet und Desktop mitdenken.
- Dynamische IDs, Slugs oder Nutzerdaten nicht als dauerhaft wiederverwendete UI-Konfiguration hardcoden.

Relevante Frontend-Prüfungen:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm test
pnpm typecheck
pnpm build
pnpm audit:language
```

Bei Änderungen an zentralen Nutzerwegen zusätzlich:

```bash
pnpm exec playwright install chromium
pnpm test:e2e
```

Für sichtbare UI-Änderungen im Pull Request nach Möglichkeit Desktop- und Mobile-Screenshots oder kurze Aufnahmen beilegen.

## Backend-Regeln

- Autorisierung, Validierung und Datenschutz immer serverseitig erzwingen.
- Öffentliche, authentifizierte und administrative Daten strikt trennen.
- Keine Zugriffskontrolle ausschließlich über versteckte Frontend-Elemente umsetzen.
- Öffentliche API-Verträge möglichst rückwärtskompatibel halten.
- GeoJSON-Eingaben verwenden EPSG:4326 in Reihenfolge Längengrad/Breitengrad.
- Räumliche Distanz-/Flächenberechnungen nur in geeigneten metrischen Koordinatensystemen durchführen.
- DB-Zugriffe über vorhandene SQLAlchemy-Session-/Service-Strukturen führen.
- Externe Provider über bestehende Service-Abstraktionen anbinden und Timeouts/Fehlerpfade berücksichtigen.
- Keine vollständigen externen Responses, Secrets oder personenbezogenen Daten ungefiltert loggen.

Relevante Backend-Prüfungen:

```bash
cd backend
uv sync --frozen --extra dev
uv run ruff check app tests
uv run pytest
uv run python -c "from app.main import app; assert app.title"
```

## Datenbank und Alembic

Für Schemaänderungen immer eine neue Alembic-Migration anlegen. Bereits veröffentlichte Migrationen nicht nachträglich ändern.

Neue Migrationen mindestens so prüfen:

```bash
cd backend
uv run alembic heads
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

Automatisch generierte Migrationen immer manuell prüfen, insbesondere bei:

- PostGIS-Geometrietypen
- Indizes und Constraints
- Datenmigrationen
- Defaults und `NOT NULL`
- potentiell destruktiven Änderungen

Destruktive Migrationen benötigen einen klaren Rollout-/Rollback-Hinweis im Pull Request.

## Sicherheit und Datenschutz

Keine Secrets, Tokens, Zugangsdaten, produktiven `.env`-Dateien, personenbezogenen Daten oder nicht öffentlichen Verwaltungsdaten committen.

Besonders schützen:

- Passwörter
- JWTs, Access-/Refresh-Tokens
- Cookies und Sessiondaten
- CSRF-Werte
- OAuth-Secrets
- MFA/TOTP-Secrets und Recovery Codes
- SMTP-Zugangsdaten
- API-Keys
- private E-Mail-Adressen
- rohe Assistant-/LLM-Anfragen mit möglicher PII

Security-Änderungen müssen bestehende Scanner und Gates respektieren. Keine `continue-on-error`-Umgehungen für Security-Jobs einführen.

Für neue Security-Ausnahmen den dokumentierten, befristeten Ausnahmeprozess in `SECURITY.md` verwenden.

Sicherheitslücken nicht in öffentlichen Issues offenlegen.

## Logging und Observability

- Strukturierte Logging-/Observability-Helfer wiederverwenden.
- Request-/Correlation-IDs nicht neu parallel implementieren.
- Keine hoch-kardinalen Werte wie User-ID, Slug, Request-ID oder Suchtext als Prometheus-Label verwenden.
- Keine Request-/Response-Bodies, Query-Strings oder Auth-Header ungefiltert loggen.
- Release-SHA aus der bestehenden Deployment-/Runtime-Konfiguration verwenden.
- Observability darf kein harter externer Runtime-Zwang werden: ein nicht erreichbarer Telemetrie-Backend darf normalen Traffic nicht blockieren.

## Externe Daten und OpenStreetMap

- Quellen, Provenienz und Lizenzinformationen erhalten.
- OpenStreetMap-Daten unterliegen weiterhin der ODbL; AGPL des Anwendungscodes ersetzt keine Datenlizenzen.
- Bei Import-/Export-Änderungen keine Lizenz- oder Herkunftsinformationen verwerfen.
- Externe API-Aufrufe müssen Timeouts, Rate Limits und Fehlerszenarien berücksichtigen.
- Keine proprietäre Pflichtabhängigkeit einführen, wenn eine offene/self-hostbare Lösung möglich ist.

## Deployment und Betrieb

Deployment ist sensibel. Vor Änderungen in `deploy/` bestehende Rollen, Templates, Rollback- und Release-Mechanismen vollständig lesen.

Insbesondere erhalten bleiben müssen:

- Deploy des exakten Commit-SHA
- versionierte Release-Verzeichnisse
- atomarer `current`-Symlink
- Pre-Migration-Backup
- Migration und Smoke Checks
- Rollback-Fähigkeit
- sichere, externe Secret-Konfiguration

Keine produktiven Werte hardcoden.

Ansible-Änderungen mindestens mit den vorhandenen Unit- und Syntaxprüfungen validieren.

## GitHub Actions und Supply Chain

- Externe GitHub Actions ausschließlich über vollständige, verifizierte Commit-SHAs referenzieren.
- Die lesbare Release-Version als Kommentar am Pin beibehalten.
- Container-Images in CI/Deployment entsprechend der bestehenden Supply-Chain-Policy per Digest pinnen.
- Bestehende `release-gate`, `security` und `supply-chain` Workflows nicht umgehen.
- Neue Dependency-Update-Pfade so gestalten, dass Pull Requests durch die vollständige CI-/Security-Pipeline laufen.

Vor Workflow-Änderungen die aktuellen Pins und `docs/supply-chain.md` prüfen.

## Dokumentation

Wenn eine sichtbare Kernfunktion geändert oder ergänzt wird, zusätzlich prüfen:

- `frontend/app/config/documentation.ts`
- Benutzertexte und Suchbegriffe
- relevante technische Dokumentation in `docs/`
- bestehende Dokumentationstests

Benutzerorientierte Dokumentation ist überwiegend deutsch. Codebezeichner und technische Kommentare dürfen englisch sein.

Keine Funktionen, Datenquellen, Zuständigkeiten oder Betriebszustände erfinden, die im Code nicht existieren.

## Pull-Request-Anforderungen

Ein Pull Request soll enthalten:

- Problem/Ausgangslage
- umgesetzte Lösung
- betroffene Bereiche
- ausgeführte Tests mit Ergebnis
- bei UI-Änderungen Screenshots für relevante Viewports
- Hinweise zu Migrationen
- Hinweise zu Konfigurationsänderungen
- Rollout-/Rollback-Hinweise bei Betriebsänderungen
- verknüpftes Issue, falls vorhanden (`Fixes #...` nur wenn vollständig erledigt)

Keine Behauptung "alle Tests grün", wenn Tests nicht tatsächlich ausgeführt wurden.

## Abschluss-Checkliste für Agents

Vor Abschluss einer Aufgabe prüfen:

- [ ] Änderung ist auf den angeforderten Umfang begrenzt.
- [ ] Bestehende Architektur wurde wiederverwendet statt dupliziert.
- [ ] Keine Secrets oder personenbezogenen Daten hinzugefügt.
- [ ] Relevante Unit-/Integrationstests ergänzt oder angepasst.
- [ ] Frontend-Typecheck/Build bei Frontendänderungen erfolgreich.
- [ ] Backend-Lint/Tests bei Backendänderungen erfolgreich.
- [ ] Migrationen bei Schemaänderungen vollständig geprüft.
- [ ] Security-/Supply-Chain-Regeln bei CI/Dependency-Änderungen eingehalten.
- [ ] Dokumentation aktualisiert, wenn Verhalten oder Betrieb betroffen ist.
- [ ] Pull-Request-Beschreibung nennt echte Testergebnisse und verbleibende Risiken.
