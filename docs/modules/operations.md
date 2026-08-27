# Operationaler Modulstatus

Der operationale Modulstatus ist eine read-only Projektion der bereits aktiven
Backend-Runtime. Er ist kein Installationsinventar und keine persistente
Lifecycle-State-Machine.

## Zwei getrennte Verträge

Das generierte Backend-Inventar bleibt der Build- und Compatibility-Contract für
den Frontend-Host:

```json
{"modules":[{"id":"analysis-areas","version":"1.0.0"}]}
```

Es enthält weiterhin ausschließlich ID und Version. Runtime-, Health-, Job- und
Origin-Daten werden dort nicht ergänzt.

Der operationale Status steht separat unter:

```text
GET /api/v1/admin/modules/status
```

Der Endpoint verwendet die bestehende Superuser-Authentifizierung, antwortet mit
`Cache-Control: private, no-store` und ist nicht Teil der öffentlichen Health-API.
Ein Snapshot sieht beispielsweise so aus:

```json
{
  "modules": [
    {
      "id": "analysis-areas",
      "version": "1.0.0",
      "status": "running",
      "enabled": true,
      "registered": true,
      "capabilities": [
        "analysis-areas.public-api",
        "analysis-areas.lookup",
        "analysis-areas.geojson"
      ],
      "dependencies": [],
      "origin": "built-in",
      "job_count": 0
    }
  ]
}
```

`loaded`, `registered` und `running` werden unmittelbar aus `ModuleRecord` und
`ModuleRuntime` abgeleitet. Es gibt keinen separat gespeicherten Status. Da nur
aktivierte, erfolgreich validierte Runtime-Records projiziert werden, ist
`enabled` immer `true`. Nicht aktivierte Built-ins werden nicht gesucht und nicht
als vermeintlich installierte Module ausgegeben.

Dependencies stammen aus den bereits validierten Manifesten und den aufgelösten
Runtime-Records. Erforderliche sowie tatsächlich vorhandene optionale Dependencies
enthalten Requirement, aufgelöste Version und `compatible: true`. Die Statuslogik
führt keine zweite SemVer- oder Graphauflösung aus. Inkompatible Manifeste brechen
weiterhin vor Erzeugung der Runtime mit `ModuleValidationError` ab.

Origins werden ausschließlich als `built-in`, `entry-point` oder `unknown`
ausgegeben. Python-Importpfade, Entry-Point-Werte, lokale Dateipfade,
Distribution-Interna, Settings, Secrets und Exception-Texte sind kein Bestandteil
des Response-Contracts. Die JobRegistry wird nur als Anzahl stabil registrierter
Jobs pro Modul projiziert; Jobhistorie und Scheduler-Dashboard existieren nicht.

## Health und Fail-fast

Die öffentlichen Endpunkte `/health/live`, `/health/ready`, `/health` und
`/health/info` bleiben unverändert. Moduldetails beeinflussen ihre Antwort nicht.
Die heutige Bootstrap-Policy bleibt dennoch fail-fast: Discovery-, Manifest-,
Compatibility-, Dependency- und Load-Fehler verhindern den Aufbau einer
halbgültigen Runtime. Registration- und Startup-Fehler bleiben strukturierte
`ModuleRuntimeError`-Unterklassen; bereits gestartete Lifecycle-Beiträge werden
beim Startup-Fehler weiterhin aufgeräumt.

Runtime-Logs verwenden `module_id`, `module_version` und `module_phase`. Job-Logs
und -Metriken behalten die dokumentierten begrenzten `module_id`, `job_id`,
`job_phase` und `result`-Dimensionen. Fehlertexte, URLs und nutzerbezogene Werte
werden nicht als Metriklabels eingeführt.

## Diagnoseablauf

1. Aktivierung in der lokalen oder deployten Environment prüfen, ohne Secret-Werte
   auszugeben:

   ```bash
   cd backend
   rg '^ENABLED_MODULES=' .env
   ```

2. Discovery, Manifest und Compatibility über den bestehenden Build-Contract
   prüfen:

   ```bash
   cd ..
   scripts/backend-module-inventory --format json
   ```

3. Den geschützten Runtime-Snapshot mit einer bestehenden Superuser-Sitzung
   abrufen. Eine lokale Cookie-Datei darf nicht committed oder protokolliert werden:

   ```bash
   curl --fail --cookie ./admin-cookie.jar \
     http://127.0.0.1:8000/api/v1/admin/modules/status
   ```

4. Registration und Startup über strukturierte Logs prüfen:

   ```bash
   sudo journalctl -u stadtplaner-api -o cat \
     | jq 'select(.module_id != null)'
   ```

5. Host-Liveness und -Readiness unabhängig prüfen:

   ```bash
   curl --fail http://127.0.0.1:8000/health/live
   curl --fail http://127.0.0.1:8000/health/ready
   ```

6. Den Migrationsgraph der aktivierten Module prüfen:

   ```bash
   cd backend
   uv run python -m app.cli.module_migrations preflight
   ```

7. `job_count` im Status mit den stabilen Job-IDs und der Telemetrie aus
   [Modulare Background Jobs](background-jobs.md) abgleichen. Es wird keine
   Jobhistorie im Status gespeichert.

8. Den bestehenden Contract- und Architektur-Gate ausführen:

   ```bash
   cd ..
   scripts/module-contract-gate
   ```

9. Bei Fehlern die `phase`, `module_id` und sichere Origin-Kategorie mit dem
   ursprünglichen `ModuleValidationError`, `ModuleRegistrationError` oder
   `ModuleStartupError` im Prozesslog korrelieren. Interne Exception-Texte werden
   bewusst nicht über den Admin-Endpoint gespiegelt.

## Scope

Dieser Status führt weder `installed`, Upgrade-/Rollback-Zustände, Enable-/Disable-
Befehle noch eine persistente Lifecycle-Datenbank ein. Installer und `modules.lock`
bleiben #173 vorbehalten, `.ocp`-Bundles #174 und eine Package Registry #175. Die
verbindliche Enable-/Disable-Semantik sowie Upgrade- und Recovery-Abläufe stehen in
der [Modul-Lifecycle-Policy](lifecycle.md). Dieser Status bleibt dabei unverändert
eine Projektion von `loaded`, `registered` und `running`.
