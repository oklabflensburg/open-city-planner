# ADR: Architektur- und Modulverträge als CI-Gate

- Status: Angenommen
- Datum: 2026-08-26
- Entscheidung: [Issue #105](https://github.com/oklabflensburg/open-city-planner/issues/105)
- Epic: [Issue #91](https://github.com/oklabflensburg/open-city-planner/issues/91)

## Kontext

Manifeste, SDKs und Registries definieren Modulgrenzen, verhindern aber allein keine
später eingeführten Direktimporte. Reine Textsuche erkennt TypeScript-Re-Exports,
dynamische Imports und mehrzeilige Syntax nicht zuverlässig. Eine große historische
Allowlist würde zugleich neue Verstöße verbergen.

## Entscheidung

Ein eigener, verpflichtender CI-Workflow prüft die Modulverträge. Python-Imports
werden über den Standardbibliotheks-AST analysiert. Frontend-Imports, Re-Exports und
dynamische Imports werden über den bereits gelockten TypeScript-Parser analysiert;
Vue-Scriptblöcke werden einzeln geparst. Es wird keine neue schwere Abhängigkeit
eingeführt.

Bestehende Contract-Tests bleiben die ausführbare Spezifikation für Manifeste,
Kompatibilität und Registries. Ein kleiner `ModuleTestHost` ergänzt isolierte
Bootstrap-Tests. Architektur-Ausnahmen sind in einer strukturierten, fail-closed
Baseline exakt benannt und mit einem Abbau-Issue verknüpft.

## Folgen

Neue Grenzverletzungen blockieren Pull Requests mit stabiler Regel-ID und
Quellposition. Backend und Frontend laufen parallel und ohne Playwright. Eine
bewusste Ausnahme erzeugt Review-Aufwand und bleibt sichtbar; pauschale Wildcards
sind nicht möglich. Das Gate migriert keine Fachdomänen und ersetzt nicht die
vollständigen Backend-, Frontend-, E2E-, Security- oder Supply-Chain-Gates.
