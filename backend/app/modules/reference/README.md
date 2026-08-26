# Reference Module

Dieses bewusst kleine Modul ist ausführbare SDK-Dokumentation. Es zeigt eine neutrale
`ReferenceItem`-Domäne vom eigenen PostgreSQL-Schema bis zur Nuxt-Seite und zum
MapLibre-Layer. Es ist kein produktives Fachfeature.

## 1. Was demonstriert dieses Modul?

Das Modul nutzt Manifest und Entry-Point-Discovery, Backend- und Frontend-SDK,
Persistence, Migration, Permission und CSRF, Settings, Domain Event, Subscriber,
Background Job, Seite, Navigation, UI-Slot, Kartenquelle, Kartenlayer und Feature-Info.
Es importiert keine fremde Fachdomäne und benötigt keinen externen Dienst.

## 2. Ordnerstruktur

```text
backend/app/modules/reference/
├── api/                 # FastAPI-Schemas und Router
├── application/         # Use Cases und Permission Enforcement
├── domain/              # Entity und Domain Event
├── persistence/         # eigene Metadata, Repository und Migration
├── module.py            # Composition Root und passive Definition
└── settings.py          # typisierte Konfiguration

frontend/frontend-modules/reference/
├── module.json          # Build-Time-Manifest und Contributions
└── layer/app/           # lokale Seite, Komponenten und Composable
```

## 3. Manifest

`module.py` definiert das Backend-Manifest V1 mit der stabilen ID `reference`, Version
`1.0.0`, Host-/SDK-Bereichen, Capabilities, Permission, Config-Namespace und
Schema-Ownership. `frontend/frontend-modules/reference/module.json` verwendet dieselbe
ID und deklariert die kompatible Backend-Version. Es wird keine neue Manifest-Version
eingeführt.

## 4. Backend Registration

Der Python-Entry-Point `open_city_planner.modules` in `backend/pyproject.toml` liefert
die passive `DEFINITION`. Erst wenn `ENABLED_MODULES=reference` gesetzt ist, lädt die
generische Runtime `ReferenceModule` und ruft `register(context)` auf. Weder
`app.main` noch der zentrale API-Router kennen die Modul-ID.

## 5. Route

Das Modul registriert selbst:

- `GET /api/v1/modules/reference/items`
- `GET /api/v1/modules/reference/items.geojson`
- `POST /api/v1/modules/reference/items`

Die GET-Routen lesen ausschließlich Beispieldaten. POST nutzt die öffentliche
Permission-Dependency des SDK und die bestehende Host-Authentifizierung samt CSRF.

## 6. Persistence

`persistence/models.py` besitzt eine eigene `MetaData(schema="reference")` und die
Tabelle `reference.items`. Das Repository erhält seine `AsyncSession` ausschließlich
über `context.database.session()`; globale Engine, Host-Base und fremde Tabellen
werden nicht importiert.

## 7. Migration

`persistence/migrations/20260826_mod_reference_0001.py` erstellt nur das Schema
`reference` und seine Tabelle und fügt zwei deterministische Marker ein. Der
`ModuleMigrationSource` verwendet den vorgeschriebenen Namespace `mod_reference`.
Der gezielte Downgrade entfernt ausschließlich die eigene Tabelle und das eigene
Schema.

## 8. Permission

Das Manifest besitzt `reference.items-write`. Die POST-Route fordert sie mit
`csrf=True`; anschließend prüft der Application-Service nochmals fail-closed über
`context.permissions`. Rollen und Superuser-Regeln bleiben vollständig Eigentum der
Host-Permission-Engine.

## 9. Settings

`ReferenceSettings` ist ein eingefrorenes Pydantic-Modell. Defaults sind
`max_items=100` und `job_interval_seconds=3600`. Overrides sind ausschließlich
namespaced:

```bash
OCP_MODULE_REFERENCE_MAX_ITEMS=50
OCP_MODULE_REFERENCE_JOB_INTERVAL_SECONDS=1800
```

Das erste Feld ist explizit öffentlich; es gibt keine Secrets.

## 10. Events

Ein erfolgreicher Create-Use-Case stellt `reference.item-created` in Version 1 mit
`item_id` und `title` über `publish_after_commit()` in die transaktionale Outbox.

## 11. Job

`reference.count-items` zählt die eigenen Datensätze und schreibt die begrenzte
Metrik `items-total`. Der Job läuft nach dem konfigurierten Intervall, hat ein
30-Sekunden-Timeout und verwendet nur Scheduler-, Database- und Observability-Ports.

## 12. Frontend Page

Das lokale Nuxt-Layer liefert `/referenzmodul`. Das modulinterne Composable lädt die
eigene API SSR-sicher über die konfigurierte API-Basis. Lade- und Fehlerzustände
bleiben verständlich und barrierearm.

## 13. Navigation

`reference.primary-navigation` trägt den öffentlichen Link deklarativ zu
`navigation.primary` bei. `reference.admin-navigation` zeigt denselben Einstieg im
Admin-Bereich nur authentifiziert mit `reference.items-write`. Die Host-Navigation
wird nicht geändert.

## 14. UI Slot

`reference.map-feature-info` rendert `ReferenceFeatureInfoControl` im vorhandenen
Slot `map.controls`. Die Komponente wird ausschließlich aus dem lokalen Layer geladen.

## 15. Map Extension

Das Frontend-Manifest registriert die zunächst leere GeoJSON-Quelle `reference.items`
und den gleichnamigen Circle-Layer in der Gruppe `overlay`. Die Slot-Komponente lädt
`/modules/reference/items.geojson` über die konfigurierte API-Basis und aktualisiert
die Quelle über den ausdrücklich öffentlichen `unsafeMapLibre()`-Escape-Hatch des
Map SDK. So funktionieren getrennte lokale Frontend-/Backend-Origins ebenso wie ein
Same-Origin-Deployment. `MapCanvas.vue` wird nicht gepatcht.

## 16. Feature Info

Die Slot-Komponente bezieht `MapContext` über `#frontend-module-sdk`, registriert den
Provider `reference.items-info` und die Klick-Interaction `reference.items-click`.
Ein Klick zeigt `title` und `description`; beim Unmount werden beide Contributions
abgemeldet.

## 17. Tests

```bash
cd backend
uv run pytest tests/modules/reference

cd ../frontend
pnpm vitest run tests/reference-module/reference-module.test.ts

cd ..
scripts/module-contract-gate
```

Die Tests decken Manifest, Compatibility, enabled/disabled, Ownership, Permission,
Event, Subscriber, Job sowie Frontend-Contributions ab. Das Architektur-Gate prüft
den Produktionscode selbst als positives Contract-Fixture.

## 18. Aktivieren

Backend und Migration:

```bash
cd backend
ENABLED_MODULES=reference uv run python -m app.cli.module_migrations preflight
ENABLED_MODULES=reference uv run python -m app.cli.module_migrations upgrade
ENABLED_MODULES=reference uv run uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
OCP_FRONTEND_MODULES=reference \
OCP_BACKEND_MODULES=reference@1.0.0 \
pnpm dev
```

Für einen Produktionsbuild gelten dieselben beiden Frontend-Variablen mit
`pnpm build`.

## 19. Deaktivieren

`reference` aus `ENABLED_MODULES`, `OCP_FRONTEND_MODULES` und dem Backend-Inventar
entfernen und Backend/Frontend neu starten beziehungsweise neu bauen. Dann fehlen
Route, Permission, Subscriber, Job, Seite, Navigation, Slot und Map-Layer. Die
Tabelle und historische Migration bleiben absichtlich erhalten; Deaktivieren löscht
keine Daten. Ein physisches Entfernen braucht eine separat geprüfte Cleanup-Migration
mit Backup- und Rollback-Plan.

## 20. How to create your own module

1. Beide Verzeichnisse kopieren, zum Beispiel
   `cp -R backend/app/modules/reference backend/app/modules/my_module` und
   `cp -R frontend/frontend-modules/reference frontend/frontend-modules/my-module`.
2. Modul-ID und Python-/Frontend-Verzeichnis, Version und Entry-Point umbenennen.
3. Manifest-, Config-, Schema- und Revision-Namespace konsistent ändern.
4. Permission-, Route-, Event-, Job-, Source-, Layer- und Contribution-IDs umbenennen.
5. Tabelle, Migration, Entity, API-Schemas und sichtbare Texte auf die neue kleine
   Domäne zuschneiden; die alte Revision-ID nicht wiederverwenden.
6. Tests kopieren und zuerst enabled, disabled und inkompatible Versionen prüfen.
7. Architektur-Gate, vollständige Tests, Typecheck und beide Builds ausführen.

Kopiere keine Host-Interna. Modulcode importiert Plattformverträge nur aus
`app.platform.modules.sdk` beziehungsweise `#frontend-module-sdk`. Wenn ein nötiger
Contract fehlt, wird das SDK bewusst erweitert; private DB-, Runtime-, Auth-, Router-,
Navigations- oder MapCanvas-Implementierungen sind keine Abkürzung.
