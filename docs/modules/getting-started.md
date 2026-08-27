# Open City Planner Module – Getting Started

> The reference module is the canonical executable SDK example.

Diese Anleitung führt zum kleinsten Built-in-Fullstack-Modul mit GET-API und
Nuxt-Seite. Das Scaffold kopiert bewusst keine Fachlogik des Reference-Moduls.
Persistence, Permissions, Events, Jobs und Map-Erweiterungen kommen erst bei Bedarf
hinzu.

## 1. Voraussetzungen

Installiere die in `.python-version`, `.node-version`, `backend/pyproject.toml` und
`frontend/package.json` festgelegten Versionen. Richte anschließend die gelockten
Abhängigkeiten ein:

```bash
cd backend
uv sync --frozen --extra dev
cd ../frontend
pnpm install --frozen-lockfile
cd ..
```

## 2. Modul erzeugen

Vom Repository-Root erzeugt dieser Befehl ein Built-in-Modul:

```bash
./scripts/create-module hello-world
```

Modul-IDs sind stabile lowercase-ASCII-IDs in Kebab Case, beginnen mit einem
Buchstaben und sind höchstens 63 Zeichen lang. `hello-world` wird für Python zu
`hello_world`; Config, Permissions, Capabilities und Contributions behalten die
öffentliche ID `hello-world`. Existierende Ziele werden nie überschrieben.

## 3. Modulstruktur verstehen

Das Scaffold erzeugt ausschließlich modulbezogene Dateien:

```text
backend/app/modules/hello_world/
├── api/
├── module.py
├── settings.py
└── README.md
backend/tests/modules/hello_world/
frontend/frontend-modules/hello-world/
├── module.json
└── layer/
frontend/tests/hello-world/
```

`module.py` exportiert die passive `ModuleDefinition`. `module.json` verwendet
dieselbe ID und deklariert Route, Navigation und Backend-Kompatibilität. Der Host
erkennt Built-in-Backends nach der Verzeichniskonvention
`app.modules.<python_name>.module:DEFINITION`; zentrale Router, `app.main`,
Navigation, AppShell und `MapCanvas.vue` bleiben unverändert.

Der vollständige Datenweg und alle optionalen SDK-Primitives stehen im
[`reference`-Modul](../../backend/app/modules/reference/README.md). Das vorhandene
`example-module` ist nur eine kompakte interne Frontend-Contract-Fixture und keine
zweite Modul-Autorenvorlage.

## 4. Backend-API weiterentwickeln

Die generierte Route `GET /api/v1/modules/hello-world/hello` liegt in
`api/router.py`. Registriere weitere Router ausschließlich über
`context.api.include_router()` und importiere Plattformverträge aus
`app.platform.modules.sdk`.

Details: [Backend Module SDK](backend-module-sdk.md),
[Manifest V1](module-manifest-v1.md) und
[Settings](configuration.md).

## 5. Frontend-Seite beitragen

Die generierte Seite ist unter `/modules/hello-world` deklariert. Neue Pages müssen
im eigenen Nuxt-Layer liegen und in `module.json` unter
`publicContributions.routes` aufgeführt sein. Navigation und UI-Slots werden
ebenfalls deklarativ beigetragen; Host-Komponenten werden nicht gepatcht.

Details: [Frontend-Host](frontend-host.md) und
[Frontend UI Contributions](frontend-ui-contributions.md).

## 6. Optional einen Map Layer beitragen

Das Scaffold startet mit leeren `map.sources` und `map.layers`. Ergänze Source und
Layer erst bei fachlichem Bedarf in `module.json`; Runtime-Interaktionen verwenden
Typen aus `#frontend-module-sdk`. IDs beginnen mit `hello-world.`.

Details und ein ausführbares Beispiel:
[Map SDK](map-sdk.md) und das
[`reference`-Frontend](../../frontend/frontend-modules/reference/README.md).

## 7. Modul lokal aktivieren

Das Backend entdeckt das Built-in-Modul ohne zentralen Entry-Point-Eintrag:

```bash
cd backend
export ENABLED_MODULES=hello-world
uv run uvicorn app.main:app --reload
```

Erzeuge in einem zweiten Terminal das reale Backend-Inventar und starte dann den
Frontend-Host:

```bash
cd backend
export ENABLED_MODULES=hello-world
export OCP_BACKEND_MODULES="$(../scripts/backend-module-inventory --format env)"
cd ../frontend
export OCP_FRONTEND_MODULES=hello-world
pnpm modules:check
pnpm dev
```

`OCP_BACKEND_MODULES` ist ein generierter ID-/Versions-Transport, keine zusätzliche
Aktivierungsentscheidung. Optionale Settings verwenden das Präfix
`OCP_MODULE_HELLO_WORLD_`.

## 8. Tests ausführen

```bash
cd backend
uv run pytest tests/modules/hello_world

cd ../frontend
OCP_FRONTEND_MODULES=hello-world \
OCP_BACKEND_MODULES=hello-world@1.0.0 \
pnpm vitest run tests/hello-world
pnpm typecheck
```

Die generierten Tests validieren das echte Backend-SDK und den realen Frontend-
Module-Contract; sie sind keine vollständigen Datei-Snapshots.

## 9. Contract Gate ausführen

```bash
cd ..
scripts/module-contract-gate
```

Das Gate kombiniert Manifest-, Runtime-, Frontend-, Map- und Architekturprüfungen.
Generierter Backend-Code darf keine Host-Interna importieren; Frontend-Code nutzt
eigene relative Dateien, `#frontend-module-sdk` oder `#imports`.

## 10. Nächste Schritte

Erweitere nur die benötigten Verträge:

- [Persistence und Migrationen](database-and-migrations.md)
- [Permissions](permissions.md)
- [Domain Events](domain-events.md)
- [Background Jobs](background-jobs.md)
- [Map Extensions](map-sdk.md)
- [Settings und Secrets](configuration.md)
- [Security und Community Review](community-module-review.md)
- [Architecture Rules](architecture-rules.md)

## Built-in und zukünftige Standalone-Module

Built-in First-Party-Module liegen heute direkt im Host-Repository:

```text
backend/app/modules/foo
frontend/frontend-modules/foo
```

Sie werden gemeinsam mit dem Host gebaut und benötigen keinen Installer. Das
Scaffold aus #110 erzeugt ausschließlich dieses Layout.

Ein zukünftig separat gepflegtes Modul soll dieselben inneren SDK-Verträge in einem
eigenen Repository bündeln:

```text
ocp-module-example/
├── module.yaml
├── backend/
├── frontend/
├── tests/
└── README.md
```

Dieses Layout ist noch kein implementiertes Paketformat. Installation und
`modules.lock` folgen in #173, das gemeinsame `.ocp` Package Bundle in #174 und die
Distribution über eine Package Registry in #175. #110 führt weder Installer,
Bundler noch Registry ein.
