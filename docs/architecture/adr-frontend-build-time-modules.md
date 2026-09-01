# ADR: Frontend-Module als Build-Time Nuxt Layers

- Status: Angenommen
- Datum: 2026-08-26
- Entscheidung: [Issue #101](https://github.com/oklabflensburg/open-city-planner/issues/101)
- Epic: [Issue #91](https://github.com/oklabflensburg/open-city-planner/issues/91)

## Kontext

Das bestehende Frontend ist eine Nuxt-4-Anwendung mit gemeinsamem SSR, Vue,
TypeScript strict, Pinia, Tailwind und einer MapLibre-Runtime. `app.vue`, das
Default-Layout, Header, Footer, globale Client-Plugins, Design-Tokens und die
globalen SEO-Defaults bilden bereits eine Host-Shell. Fachseiten, Fachkomponenten,
Stores und Composables liegen dagegen noch gemeinsam unter `frontend/app`.

Die Navigation wird derzeit zentral durch `useSiteNavigation` aufgebaut. Globale
Middleware behandelt plattformweite Weiterleitungen; fachliche Zugriffsmiddleware
ist routengebunden. Öffentliche Seiten werden serverseitig gerendert und verwenden
`useModuleSeo` für Canonical-, OpenGraph-, Twitter- und strukturierte Metadaten. #101
migriert keine dieser bestehenden Domänen, sondern schafft nur einen additiven
Integrationspfad.

## Entscheidung

Frontend-Module werden ausschließlich **vor dem Nuxt-Build** aus lokalen,
deklarativen Definitionen entdeckt und als Nuxt Layers eingebunden:

```text
OCP_FRONTEND_MODULES
        |
        v
lokale Manifest-Discovery
        |
        v
Validierung und deterministische Reihenfolge
        |
        v
Nuxt extends mit lokalen Layer-Pfaden
        |
        v
ein gemeinsamer SSR-/TypeScript-/Tailwind-/Pinia-Build
```

Es gibt keine Runtime-Microfrontends, keine Module-Federation-Remotes, keine
URL-basierten Imports, keine Script-Injection und keinen nachträglichen Fetch von
Vue-Code. Nur Module, die bereits im Build-Workspace vorhanden und explizit
aktiviert sind, können in das Bundle gelangen.

## Warum Nuxt Layers

Nuxt Layers integrieren Pages, Components, Composables, Stores und nicht-globale
Middleware in denselben Nuxt-Compiler. Dadurch bleiben SSR, SEO, TypeScript,
Tailwind, Pinia, HMR und Dependency-Deduplizierung Eigenschaften einer Anwendung.
Eine eigene Layer-Pipeline oder ein zweiter Vue-Root wäre dafür unnötig.

Der lokale Katalog heißt `frontend/frontend-modules/`. `frontend/modules/` wird
nicht verwendet, weil Nuxt diesen Namen für lokale Nuxt-Buildmodule reserviert und
diesen Baum beim Page-Scan anders behandelt. Jeder Katalogeintrag besitzt einen
kleinen Layer und eine rein deklarative `module.json`; `nuxt.config.ts` kennt keine
fachliche ID, sondern nur die generische Discovery.

Nuxt Layers allein definieren keine Ownership. Deshalb prüft der Host zusätzlich
das Manifest, alle Page-Beiträge und verbietet in V1 module-owned `app.vue`,
Layouts, globale Plugins, globale Middleware, Server-Handler und lokale Nuxt-
Buildmodule. Nicht-globale fachliche Middleware bleibt möglich. Weitere globale
Extension Points benötigen später einen expliziten Host-Contract.

## Modulcontract und Versionierung

`FrontendModuleDefinition` und `FrontendModuleCompatibility` sind der öffentliche
TypeScript-Contract. `FRONTEND_MODULE_SDK_VERSION` startet mit `1.0.0`. Der Contract
enthält nur:

- Schema-, Modul- und optionale Backend-Modulidentität;
- vollständige Modulversion;
- Compatibility-Ranges für Host, Frontend-SDK und optionales Backend-Modul;
- lokalen Layer-Pfad;
- kleine Modulabhängigkeitsmenge;
- öffentliche Routenmetadaten;
- optionale statische und dynamische Sitemap-Contributions für bereits deklarierte
  Routen.

IDs spiegeln die Backend-Regel aus #93: lowercase kebab-case, maximal 63 Zeichen.
Ein Fullstack-Modul verwendet auf beiden Seiten dieselbe ID. Versionen und Ranges
werden nicht durch eine eigene SemVer-Engine ausgewertet, sondern durch die
etablierte npm-Bibliothek `semver`. Eine inkompatible Host-, SDK-, Backend- oder
Modulversion beendet den Preflight.

Die SDK-Version folgt SemVer. Rückwärtskompatible Contract-Erweiterungen erhöhen
Minor, inkompatible Änderungen Major. Die Version eines Fachmoduls bleibt davon
getrennt. Ein optionaler `backend`-Range beschreibt die kompatible Version desselben
Fullstack-Moduls, nicht eine zweite Modulidentität.

## Discovery, Enablement und Reihenfolge

`OCP_FRONTEND_MODULES` enthält eine komma-separierte Liste stabiler IDs. Leer oder
nicht gesetzt bedeutet: kein optionales Frontend-Modul. Discovery liest nur lokale
`module.json`-Dateien, sortiert Quellen und IDs deterministisch und schlägt bei
fehlenden Modulen oder doppelten IDs fail-fast fehl. Gleicher Commit und gleiche
Aktivierung ergeben damit dieselbe Layer-Reihenfolge.

Erforderliche Frontend-Module werden mit SemVer-Ranges deklariert. Eine kleine
topologische Sortierung stellt Dependencies vor Consumer; fehlende, inkompatible
oder zyklische Abhängigkeiten sind Buildfehler. Dies spiegelt die grundlegende
Dependency-Logik aus #93, ohne dessen Backend-Manifest oder Graph-Runtime zu
duplizieren.

`OCP_BACKEND_MODULES` ist ein optionaler Build-/Deployment-Preflight-Snapshot im
Format `id` oder `id@version`. Ist er gesetzt, muss jedes aktivierte Fullstack-
Frontend-Modul darin vorkommen; vorhandene Versionen werden gegen den Backend-
Range geprüft. Der Snapshot wird aus `ENABLED_MODULES`, der bestehenden Backend-
Discovery und den validierten Backend-Manifests generiert; er ist keine manuell
gepflegte Aktivierungskonfiguration. Serverseitige Autorisierung bleibt unabhängig
davon verbindlich.

## Routing, SSR und SEO

Jede Modulpage wird mit Route und lokaler Quelldatei deklariert. Der Preflight
gleicht diese Metadaten gegen den Layer-Pagebaum ab. Undeklarierte Pages, fehlende
Quelldateien, doppelte Modulrouten und Kollisionen mit Host-Pages stoppen den Build.
Eigene `definePageMeta`-Pfade sind in V1 nicht Teil des Contracts.

Modulpages laufen im normalen Nuxt-SSR und verwenden die vorhandenen Host-
Primitives wie `useModuleSeo`. Fachliche SEO-Metadaten gehören zur Seite; globale
Defaults und die SEO-Infrastruktur bleiben Host-owned. Browser-APIs benötigen wie
im Host weiterhin Client-Guards.

## TypeScript, Tailwind und Pinia

Alle Layer werden vom gemeinsamen Strict-Typecheck geprüft. `skipLibCheck`,
`ts-ignore` oder ein zweiter TypeScript-Build sind kein Integrationsmechanismus.
Module verwenden die bestehende Tailwind-Vite-Pipeline und die Host-Design-Tokens;
eine separate CSS-/UI-Framework-Pipeline ist nicht vorgesehen. Modulstores nutzen
die einzige durch `@pinia/nuxt` installierte Pinia-Instanz.

Module dürfen eigene Interna direkt importieren. Direkte Deep Imports in andere
Module oder Host-Interna sind nicht erlaubt; stabile modulübergreifende UI-
Contracts folgen erst mit den Extension Points. Der Host importiert niemals ein
konkretes Modul.

## Ownership

Host-owned bleiben `app.vue`, AppShell, globale Error-/Layout-Basis, Branding,
Design-Tokens, Tailwind-/Pinia-/Nuxt-Konfiguration, globale Plugins und Middleware,
SSR-/SEO-Infrastruktur sowie Discovery und Preflight. Module besitzen ihre
Fachpages, Komponenten, Composables, Stores, routengebundene Middleware und
fachlichen SEO-Inhalte.

Das Example-Modul ist ausschließlich ein Architekturbeweis. Bestehende Statistics-,
Polygon-, Auth-, OSM-, Assistant- und Analysis-Area-Seiten bleiben unverändert.

## Folgen und Grenzen

- Ein deaktiviertes Modul wird nicht an Nuxt `extends` übergeben und erzeugt keine
  Route oder Runtime-Registrierung.
- Aktivierung ist Build-Konfiguration; eine Änderung erfordert einen neuen Build.
- Shared Dependencies bleiben im Host-Bundle und werden nicht pro Modul isoliert.
- Discovery fügt nur synchrone lokale Dateiprüfungen vor dem bestehenden Nuxt-
  Lifecycle hinzu und erzeugt keinen Runtime-Failure-Mode.
- Navigation und UI Slots sind additiv im [Folge-ADR zu Frontend UI Extension
  Points](adr-frontend-ui-extension-points.md) definiert.
- MapLibre Sources, Layers, Controls und Interaktionen folgen in #103.
- Externe Paketdistribution und Signierung folgen nicht in #101.

Rollback erfolgt durch einen Build ohne `OCP_FRONTEND_MODULES` oder durch Deployment
des vorherigen Releases. Es gibt keine Datenmigration und keine irreversible
Runtime-Konfiguration.
