# Modul-Lifecycle-Policy und Runbook

Diese Policy beschreibt den vorhandenen deploy-time Lifecycle. Sie führt weder eine
persistente State Machine noch einen Installer ein. Maßgeblich bleiben die
bestehende [Backend-Runtime](backend-module-runtime.md), der
[Frontend-Host](frontend-host.md), der
[MigrationCoordinator](database-and-migrations.md) und der read-only
[operationale Status](operations.md).

## Zustände und Reihenfolge

Ein Modul ist in V1 nur für den konkreten Release konfiguriert oder nicht
konfiguriert. `installed but disabled` ist noch kein persistierter Plattformzustand.
Die beobachtbaren Runtime-Fakten bleiben `loaded`, `registered` und `running`.

Der Backend-Ablauf ist verbindlich:

```text
configured/enabled
→ discovery
→ manifest parsing
→ host/sdk compatibility
→ dependency resolution
→ settings validation
→ migration preflight
→ migration upgrade
→ module loading
→ registration
→ startup
→ running
→ shutdown
```

Manifest-, Compatibility-, Dependency- und Settingsfehler stoppen den Release vor
Migration und Startup. Der Migrations-CLI verwendet dafür dieselbe passive
Discovery, Manifestauflösung und Settings Registry wie die Runtime; Runtimecode wird
dabei nicht geladen. `MigrationCoordinator.upgrade()` wiederholt den statischen
Graph-Preflight, prüft anschließend den aktuellen DB-Head gegen den installierten
Graphen und führt erst dann Revisionen aus.

Runtime-Enablement und Verfügbarkeit der Migrationshistorie sind dabei zwei getrennte
Mengen. Compatibility, Required/Optional Dependencies und Settings werden nur für
die IDs aus `ENABLED_MODULES` als Runtime-Vertrag validiert. Der Alembic-Graph erhält
dagegen die passiven Persistence Contributions aller lokal verfügbaren Built-ins und
installierten Modul-Entry-Points. Dadurch bleibt eine Revision lesbar, wenn ihr Modul
deaktiviert ist oder nicht mehr zur aktuellen Host-/SDK-Version passt. Das lädt
weder den `ModuleDefinition.loader` noch Router, Jobs oder andere Runtime-Beiträge.

Die Runtime registriert Contributions in Dependency-/Load-Reihenfolge, startet
Lifecycle-Hooks in derselben Reihenfolge und beendet sie umgekehrt. Einen
Registration-Fehler behandelt der Host fail-fast; der betreffende Prozess wird
nicht in Betrieb genommen. Bei einem Startup-Fehler werden bereits gestartete Hooks
umgekehrt aufgeräumt. Ein Cleanup-Fehler verdeckt den ursprünglichen Startup-Fehler
nicht.

## Enable

Enable ist ein neuer Build beziehungsweise ein Deployment, kein Hot-Reload.

Backend:

1. Modul-ID zu `ENABLED_MODULES` hinzufügen.
2. Backend-Inventar erzeugen und Manifest, Host-/SDK-Kompatibilität sowie Required
   und vorhandene Optional Dependencies prüfen.
3. Modulsettings über die vorhandene Settings Registry validieren.
4. Datenbankbackup entsprechend dem Migrationsrisiko erstellen.
5. `python -m app.cli.module_migrations preflight` und danach `upgrade` ausführen.
6. Release starten; Registration, Startup und operationalen Status prüfen.

Frontend:

1. dieselbe Fullstack-ID zu `OCP_FRONTEND_MODULES` hinzufügen;
2. `OCP_BACKEND_MODULES` aus dem Backend-Inventar erzeugen;
3. Frontend-Manifest, Compatibility, Dependencies, Routen und Contributions mit
   `pnpm modules:check` prüfen;
4. Nuxt-Layer bauen und das zusammengehörige Release deployen.

Ein aktiviertes Frontend ohne erforderliches Backend schlägt im Preflight fehl. Ein
Backend darf ohne Frontend laufen, sofern sein eigener Vertrag kein Frontend
voraussetzt.

## Disable und Re-Enable

Disable bedeutet, die ID aus `ENABLED_MODULES` und – falls vorhanden – aus
`OCP_FRONTEND_MODULES` zu entfernen und Backend beziehungsweise Frontend neu zu
starten oder zu bauen. Das Backend entdeckt oder lädt das Modul nicht. Damit fehlen
Router, Jobs, Event-Subscriber, Permissions und Lifecycle-Hooks. Im Frontend fehlen
Nuxt-Layer, Pages, Navigation, UI-Slots sowie Map Sources und Layers.

Disable löscht weder Tabellen noch Daten und startet keinen Downgrade. Bereits
angewandte Revisionen und ihre lokal verfügbaren Migrationsquellen bleiben Teil des
installierten Release-Graphen. Built-ins werden dafür generisch aus
`backend/app/modules/*/module.py` abgeleitet; installierte Third-Party-Module aus der
bestehenden Entry-Point-Gruppe `open_city_planner.modules`. Diese passive Discovery
ist kein persistentes Package Inventory. Package-Entfernung und explizites
Daten-Cleanup gehören zum späteren Installer-Lifecycle.

Beim Re-Enable wird die ID wieder konfiguriert und der vollständige Preflight
wiederholt. Bereits angewandte Revisionen werden erkannt; vorhandene Daten werden
weiterverwendet und nicht neu initialisiert.

## Dependencies

Eine deaktivierte Required Dependency ist ein Validierungsfehler vor Registration.
Eine fehlende Optional Dependency ist zulässig; ist sie vorhanden, wird ihre
Version geprüft und sie wird vor dem Consumer geordnet. Der Frontend-Vertrag besitzt
derzeit ausschließlich Required Module Dependencies und verhält sich entsprechend
fail-fast.

## Migration, Downgrade und Recovery

Eine zur Aktivierung ausgewählte, statisch inkompatible Modulversion darf keine
Migration auslösen. Der Preflight prüft einen globalen Alembic-Head, auflösbare
Migrationsquellen, Schema-Ownership, Revision-Namespaces und die
Dependency-Reihenfolge. Ein ungültiger aktueller DB-Head stoppt `upgrade()` vor der
ersten neuen Revision.

Diese Compatibility-Regel gilt für die neu aktivierte Version. Eine deaktivierte,
lokal noch verfügbare Version wird nur strukturell als passive Migrationsquelle
gelesen und erzwingt keine Runtime-Kompatibilität oder Settings. So kann der Graph
einen bereits angewandten alten Head weiterhin erkennen.

Downgrade ist kein Disable- oder Rollback-Nebeneffekt. Er benötigt immer eine
explizite Zielrevision, ein aktuelles Backup sowie eine geprüfte Datenverlust- und
Kompatibilitätsbewertung. Weder Disable noch Startup-Fehler, Prozessstart oder
Code-Rollback führen automatisch `MigrationCoordinator.downgrade(target_revision)`
aus.

Wenn eine Migration erfolgreich war, Registration oder Startup danach aber
fehlschlägt, gilt das Deployment als fehlgeschlagen. Runtime-Cleanup beendet nur
bereits gestartete Lifecycle-Contributions; der Datenbankstand bleibt auf der neuen
Revision. Vorgehen:

1. Fehlerphase, `module_id`, Origin-Kategorie und ursprüngliche Exception in den
   strukturierten Logs bestimmen.
2. `python -m app.cli.module_migrations preflight` sowie den aktuellen
   `alembic_version`-Stand prüfen.
3. Falls der Prozess weit genug gestartet ist, den geschützten operationalen Status
   prüfen; andernfalls sind die Bootstrap-Logs maßgeblich.
4. Einen Forward-Fix bevorzugen.
5. Code nur zurückrollen, wenn die vorherige Version nachweislich mit dem neuen
   Schema kompatibel ist.
6. Die Datenbank nur explizit auf eine geprüfte Zielrevision downgraden.

Schlägt eine Migration selbst fehl, startet die Runtime nicht. Der Coordinator
meldet Modul, Schema und Phase; der Operator prüft den teilweise erreichten
Revisionsstand und entscheidet anhand Backup und Migrationsreview über Forward-Fix
oder explizite Recovery.

## Runbook

Enable:

```bash
cd backend
export ENABLED_MODULES=reference
uv run python -m app.cli.module_inventory --format json
uv run python -m app.cli.module_migrations preflight
uv run python -m app.cli.module_migrations upgrade
export OCP_BACKEND_MODULES="$(../scripts/backend-module-inventory --format env)"
cd ../frontend
export OCP_FRONTEND_MODULES=reference
pnpm modules:check
pnpm build
```

Nach Deploy `GET /api/v1/admin/modules/status`, relevante Routen, Jobs und Logs
prüfen.

Disable:

1. ID aus beiden Enable-Variablen entfernen.
2. Frontend neu bauen und Backend neu starten.
3. Migrations-Preflight und idempotentes Upgrade gegen den weiterhin vollständigen
   lokalen Graphen ausführen.
4. Status, Routen und Contributions auf Abwesenheit prüfen.
5. DB-Revision und erwartete Moduldaten unverändert bestätigen.

Re-Enable:

1. ID wieder hinzufügen.
2. Inventar, Settings, Compatibility und Migration-Preflight erneut prüfen.
3. `upgrade` idempotent ausführen und Release deployen.
4. Status sowie vorhandene Daten prüfen.

## Scope

Installer, `modules.lock`, `.ocp`-Bundles, Registry, Marketplace, Uninstall und ein
persistenter `installed but disabled`-Zustand folgen frühestens in #173 bis #175.
Diese Policy ergänzt keine Lifecycle-Datenbank, automatische DB-Rollbacks,
Package-Downloads, Admin-UI oder Runtime-Hot-Reload.
