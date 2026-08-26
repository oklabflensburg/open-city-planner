# End-to-End-Referenzmodul

Das installierbare Modul `reference` ist die ausführbare Entwicklerdokumentation für
die Backend- und Frontend-Module-SDKs. Es ergänzt das bewusst minimale
`example-module`: Das Example bleibt ein schnelles Frontend-Contract-Fixture, während
`reference` den vollständigen Datenweg demonstriert.

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
Aktivierung, Entfernung und Copy Guide steht im
[README des Moduls](../../backend/app/modules/reference/README.md).

Für die lokale Contract-Prüfung:

```bash
scripts/module-contract-gate
```
