# Verbindliche Modul-Architekturregeln

Die maschinenlesbare Quelle ist
[`architecture/module-contract-rules.json`](../../architecture/module-contract-rules.json).
Regel-IDs bleiben stabil, damit CI-Fehler, Baseline-Einträge und Issues eindeutig
aufeinander verweisen.

| Regel | Warum | Erlaubtes Beispiel | Verbotenes Beispiel | Durchsetzung |
| --- | --- | --- | --- | --- |
| `ARCH-BASELINE-001` | Schulden bleiben sichtbar und abbaubar. | exakte Ausnahme mit `reason` und `#108` | `target: "app.*"` | Baseline-Validator und Negativtests |
| `ARCH-BE-HOST-001` | Der Host bleibt fachneutral. | `app.platform.modules.sdk` und explizite Infrastrukturadapter | Host importiert `app.services.statistics` | Python-AST-Checker |
| `ARCH-BE-MODULE-001` | Provider können ihre Interna ändern. | Alpha importiert `beta.contracts` | Alpha importiert `beta.internal` | Python-AST-Checker |
| `ARCH-BE-PRIVATE-001` | Host-Ports halten Lifecycle und Architekturgrenzen nachvollziehbar. | Modul importiert `app.platform.modules.sdk` | Modul importiert `app.db.session` oder `modules.runtime` | Python-AST-Checker |
| `ARCH-BE-SECRET-001` | Secrets bleiben namespaced und auditierbar. | Modul liest `ModuleContext.settings` | Modul liest `os.environ`, dotenv oder eigene `BaseSettings` | Python-AST-Checker |
| `ARCH-FE-HOST-001` | Der Build-Time-Host bleibt generisch. | Host liest Contribution-Registries | `nuxt.config.ts` importiert `example-module` | TypeScript-AST-Checker |
| `ARCH-FE-MODULE-001` | Nuxt-Layer bleiben unabhängig. | eigene relative Datei, `#frontend-module-sdk` oder `#imports` | `~/stores/auth` oder `../../beta/internal` | TypeScript-AST-Checker |
| `CONTRACT-MANIFEST-001` | Discovery muss deterministisch und kompatibel scheitern. | gültige ID, SemVer und SDK-Range | unbekanntes Feld oder SDK `>=99` | Backend- und Frontend-Contract-Tests |
| `CONTRACT-REGISTRY-001` | Contributions benötigen eindeutige Ownership. | eine namespacete ID vor dem Seal | doppelte ID oder Registrierung nach Seal | Registry-Contract-Tests |
| `CONTRACT-COMPAT-001` | Startreihenfolge darf nicht implizit sein. | `A -> B -> C` mit passenden Versionen | `A -> B -> A` oder fehlendes B | Manifest-/Discovery-Tests |
| `CONTRACT-TESTHOST-001` | Module sollen schnell und isoliert testbar sein. | Bootstrap mit SDK-Fakes | Test benötigt App, DB, Redis oder Internet | `ModuleTestHost`-Tests |

Der Checker meldet Regel-ID, Datei, Zeile und Zielimport. Neue Regeln benötigen
eine stabile ID, Positiv- und Negativtests sowie eine Aktualisierung dieser Tabelle.
Diese Regeln sind statische Architekturkontrollen, keine Python-, Prozess- oder
OS-Sandbox. In-Process-Module müssen nach der
[Trust-ADR](../architecture/adr-module-trust-model.md) vollständig vertrauenswürdig
sein.

## Baseline

[`architecture/module-boundary-baseline.json`](../../architecture/module-boundary-baseline.json)
ist keine allgemeine Allowlist. Jeder Eintrag benennt exakt `rule`, `source` und
`target`, enthält einen sachlichen `reason` und ein `tracking_issue` im Format
`#123`. Wildcards sind unzulässig; nicht mehr existierende Quelldateien und doppelte
Einträge brechen das Gate. Neue Ausnahmen sollen im selben Pull Request ein
Abbau-Issue und einen verantwortbaren Migrationspfad erhalten.

Die vorhandene Ausnahme für den zentralen Legacy-Persistence-Import bleibt bis
[#108](https://github.com/oklabflensburg/open-city-planner/issues/108) bestehen.
