# Frontend-Host und Build-Time-Module

Der Nuxt-Host integriert optionale Frontend-Module vor `dev`, `typecheck` und
`build`. Die Architekturentscheidung und ihre Grenzen stehen im
[Frontend-Modul-ADR](../architecture/adr-frontend-build-time-modules.md).

## Verzeichnis und Definition

Lokale Module liegen außerhalb des von Nuxt reservierten `modules/`-Verzeichnisses:

```text
frontend/frontend-modules/example-module/
├── module.json
├── README.md
└── layer/
    ├── nuxt.config.ts
    └── app/
        ├── pages/
        ├── components/
        ├── composables/
        ├── stores/
        └── middleware/
```

`module.json` ist eine deklarative, nicht ausführbare Build-Definition. Der
typisierte Contract liegt in `frontend/module-host/contract.ts`:

```json
{
  "schemaVersion": 1,
  "id": "example-module",
  "version": "1.0.0",
  "compatibility": {
    "host": ">=1.0.0 <2.0.0",
    "sdk": ">=1.0.0 <2.0.0"
  },
  "layer": "layer",
  "requires": { "modules": {} },
  "publicContributions": {
    "routes": [
      {
        "path": "/module-example",
        "source": "layer/app/pages/module-example.vue"
      }
    ]
  }
}
```

Eine Fullstack-Definition ergänzt `backendModuleId` mit exakt derselben ID und
optional `compatibility.backend`. Modul-, Host- und SDK-Versionen sind vollständige
SemVer-Versionen; Compatibility- und Dependency-Werte sind npm-SemVer-Ranges.

## Aktivieren und prüfen

Ohne Variable sind alle optionalen Module deaktiviert:

```bash
cd frontend
pnpm modules:check
pnpm build
```

Das Example-Modul wird ausschließlich zur Build-Zeit aktiviert:

```bash
OCP_FRONTEND_MODULES=example-module pnpm modules:check
OCP_FRONTEND_MODULES=example-module pnpm dev
OCP_FRONTEND_MODULES=example-module pnpm typecheck
OCP_FRONTEND_MODULES=example-module pnpm build
```

`nuxt.config.ts` ruft denselben Preflight selbst auf. Ein direkter `nuxt dev`- oder
`nuxt build`-Aufruf kann die Prüfung daher nicht umgehen. Die aktivierten IDs werden
getrimmt, dedupliziert und sortiert. Ein unbekanntes aktiviertes Modul ist immer ein
Fehler; es gibt kein Silent Skip.

Für Fullstack-Deployments kann der Build das Backend-Inventar prüfen:

```bash
OCP_FRONTEND_MODULES=statistics \
OCP_BACKEND_MODULES=statistics@2.1.0 \
pnpm modules:check
```

Ist `OCP_BACKEND_MODULES` gesetzt, fehlen aktivierte Backend-Gegenstücke nicht
stillschweigend. Ohne Versionssuffix wird nur Enablement, mit `@<version>` zusätzlich
der deklarierte Backend-Range geprüft. Die Werte enthalten keine Secrets.

## Was der Preflight validiert

- Schema, stabile IDs und vollständige Modulversionen;
- doppelte Quellen derselben ID;
- aktivierte, aber nicht vorhandene Module;
- Host-, Frontend-SDK- und optionale Backend-Kompatibilität;
- fehlende, inkompatible oder zyklische Modulabhängigkeiten;
- lokale Layer- und Page-Quellen ohne Verzeichnisausbruch;
- vollständige Deklaration aller Modulpages;
- Routenkollisionen zwischen Modulen und mit Host-Pages;
- V1-Grenzen gegen module-owned AppShell, Layouts, globale Plugins, globale
  Middleware, Server-Handler und Nuxt-Buildmodule.

Fehler nennen Modul-ID und relevante Quellen. Die Reihenfolge ist topologisch und
innerhalb gleicher Dependency-Stufen lexikografisch stabil.

## Gemeinsame Runtime-Primitives

Ein aktivierter Layer wird durch denselben Nuxt-Build verarbeitet wie der Host:

- Pages sind SSR-fähige Nuxt-Pages und können `usePageSeo` verwenden.
- Komponenten verwenden die vorhandenen Host-Komponenten und Design-Tokens.
- Tailwind wird einmal durch die vorhandene Vite-Konfiguration kompiliert.
- Stores verwenden die gemeinsame Pinia-Instanz.
- Composables und routengebundene Middleware bleiben module-owned.
- Browser-only Code benötigt weiterhin `import.meta.client`, `ClientOnly` oder
  geeignete Lifecycle-Guards.

Das `example-module` demonstriert Page, Component, Composable und Store, registriert
aber bewusst keine Navigation. Die Route ist `noindex`, weil sie nur ein technischer
Architekturbeweis ist.

## Neues Modul hinzufügen

1. Verzeichnis mit stabiler, backendkompatibler ID anlegen.
2. `module.json` vollständig erstellen und SDK-Range setzen.
3. lokalen Nuxt Layer mit deklarierter Page anlegen.
4. jede Page samt daraus abgeleiteter Route in `publicContributions.routes` nennen.
5. Modul mit `OCP_FRONTEND_MODULES` aktivieren und Preflight, Tests, Typecheck und
   beide Buildzustände prüfen.
6. bei einem Fullstack-Modul das Backend-Inventar im Deployment konsistent setzen.

Der Host wird dafür nicht um fachliche Imports oder eine ID-Liste erweitert.

## Bewusste Grenzen von V1

Der Contract enthält noch keine Navigation-/UI-Slot-Registry (#102) und keine Map-
Extension-Points (#103). Module dürfen keine unbekannten Bundles nachladen, keine
eigene Pinia-Root oder Tailwind-Pipeline starten und nicht direkt in Interna anderer
Module importieren. Externe npm-Pakete können später als bereits installierte,
lokale Quellen an denselben Contract angebunden werden; Download und Packaging sind
nicht Teil von #101.
