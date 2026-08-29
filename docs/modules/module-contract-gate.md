# Modul-Contract-Gate

Das Gate schützt den modularen Host gegen schleichende Rückkopplungen. Es kombiniert
statische Importgrenzen mit den bestehenden Manifest-, Dependency-, Registry-,
Permission-, Map- und SSR-Vertragstests. Es startet keine Browser und benötigt weder
PostgreSQL noch Redis oder externe Netzwerke.

Zusätzlich belegt das Gate, dass Repository-Module Secrets nicht direkt aus der
Prozessumgebung laden. Diese Architekturgrenze verspricht keine In-Process-Sandbox.
Provenance und Integrität späterer Third-Party-Artefakte werden am Installer-/
Deploymentrand geprüft (#173 und #174), nicht in der Runtime.

Für ausgecheckte oder entpackte First-Party-Module prüft
`scripts/check_external_module_imports.py <python-package-root>` zusätzlich die
Regel `ARCH-BE-INSTALLED-001`. Erlaubt ist aus `app.*` ausschließlich
`app.platform.modules.sdk`; damit kann dieselbe Negativregel vor Wheel-Build und
nach Installation auf den tatsächlichen Paketinhalt angewendet werden.
`ARCH-BE-PORT-OWNERSHIP-001` prüft zusätzlich alle öffentlichen
Modul-Port-Adapter unter `app.integrations`: Sie dürfen das entfernbare Built-in
`app.modules.analysis_areas` nicht importieren. Ein separater Importtest blockiert
dieses Package vollständig und lädt anschließend `module_host_ports` neu.

Nach der Installation der gelockten Backend- und Frontend-Abhängigkeiten reicht lokal:

```bash
scripts/module-contract-gate
```

Für eine einzelne Seite können `backend` oder `frontend` als Argument übergeben
werden. Das vollständige Gate soll auf Entwicklerrechnern und in CI in wenigen
Minuten laufen. Der lokale Referenzlauf für die fokussierte Matrix benötigte rund
45 Sekunden (227 Backend- und 41 Frontend-/SSR-Contract-Tests); CI führt beide
Seiten parallel aus.

GitHub Actions führt Backend und Frontend parallel aus. Der stabile aggregierte
Required Check heißt `Module contract gate`. Er ist zusätzlich Bestandteil des
`Release gate`; Fehler werden nicht als optional behandelt.

## Test-Fixtures und Test-Host

Negativ-Fixtures liegen unter `backend/tests/fixtures/module_contracts` und
`frontend/tests/fixtures/module-contracts`. Sie beweisen unter anderem, dass Zyklen,
eine inkompatible SDK-Version und ein Export aus einem fremden Frontend-Modul den
Check tatsächlich fehlschlagen lassen.

`ModuleTestHost` in `app.platform.modules.testing` lädt eine `ModuleDefinition`,
validiert Manifest und Kompatibilität, stellt die vorhandenen Fakes bereit und
schließt/sealt die Registrierung. Damit lassen sich Modul-Bootstrap und Lifecycle
ohne FastAPI-App, Datenbank, Redis oder echte HTTP-Aufrufe testen.

Regeln und Baseline-Verfahren sind in
[`architecture-rules.md`](architecture-rules.md) dokumentiert. Fachliche
Legacy-Bereinigung bleibt Aufgabe von #108; das Gate erweitert nicht den Scope der
Modularisierung.

## Typische Fehler beheben

- `ARCH-BE-MODULE-001`: öffentlichen `contracts`-Namespace oder Service Registry
  statt fremder Interna verwenden.
- `ARCH-BE-PRIVATE-001`: passenden `ModuleContext`-/SDK-Port statt Host-Session,
  Settings oder Runtime-Helper verwenden.
- `ARCH-BE-SECRET-001`: namespacetes `ModuleContext.settings` statt `os.environ`,
  dotenv oder eines eigenen Environment-Loaders verwenden.
- `ARCH-FE-HOST-001`: UI-, Navigation- oder Map-Contribution registrieren, statt
  eine konkrete Modul-ID im Host zu verzweigen.
- `ARCH-FE-MODULE-001`: `#frontend-module-sdk`, `#imports` oder eigene lokale
  Dateien verwenden.
- Inkompatibles SDK/Manifest: deklarierte Range nur anpassen, wenn das Modul den
  tatsächlich installierten öffentlichen Contract unterstützt.
