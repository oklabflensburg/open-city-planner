# End-to-End-Referenzmodul

Das Built-in-Modul `reference` ist die kanonische ausführbare
Entwicklerdokumentation für die Backend- und Frontend-Module-SDKs:

> The reference module is the canonical executable SDK example.

Es ist kein produktives Fachmodul. Das vorhandene `example-module` bleibt lediglich
eine schnelle interne Frontend-Contract-Fixture; neue Module beginnen mit dem
[Getting-Started-Scaffold](getting-started.md), während `reference` den vollständigen
Datenweg demonstriert.

```text
reference.items
    │ eigene Migration und Tabelle
    ▼
Application-Service ── Permission / Event / Job über ModuleContext
    │
    ▼
/api/v1/modules/reference/items(.geojson)
    │
    ▼
lokales Nuxt-Layer ── Seite / Navigation / UI-Slot / Map / Feature-Info
```

Der Host kennt dabei ausschließlich Entry-Points und öffentliche Contracts. Es gibt
keinen Reference-Import im zentralen Router, in der Navigation oder im `MapCanvas`.
Die vollständige, mit dem Code synchron gehaltene Anleitung einschließlich
Aktivierung und Entfernung steht im
[README des Moduls](../../backend/app/modules/reference/README.md).

Das Reference-Modul bleibt bewusst im Host-Repository und erhält in #113 keinen
eigenen Paketbuild. Die [Distribution Policy](distribution.md) beschreibt, wie
dieselben Contracts später in einem Standalone-Modul paketiert werden können.

Für die lokale Contract-Prüfung:

```bash
scripts/module-contract-gate
```
