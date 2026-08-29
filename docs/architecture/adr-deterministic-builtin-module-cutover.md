# ADR: Deterministischer Built-in-zu-Package-Cutover

- Status: Angenommen
- Datum: 2026-08-29
- Entscheidung: [Issue #188](https://github.com/oklabflensburg/open-city-planner/issues/188)

## Kontext

Built-ins und separat installierte First-Party-Pakete können während einer
Externalisierung dieselbe stabile Modul-ID besitzen. Implizite Priorität nach
Discovery-Reihenfolge würde Backend, Migrationen und Frontend unterschiedlich
zusammensetzen und einen unsicheren Fallback erzeugen.

## Entscheidung

`OCP_EXCLUDED_BUILTIN_MODULES` ist eine komma-separierte, strikt validierte Liste
stabiler Modul-IDs. Sie entfernt ausschließlich Built-in-Composition-Sources vor
Duplicate-ID-Validierung:

```text
Built-in candidates ── exclusion ──┐
                                  ├─ duplicate validation ─ composition
Installed candidates ─────────────┘
```

Backend und Frontend parsen denselben Wert an ihrer jeweiligen Systemgrenze.
Ungültige, doppelte oder unbekannte Built-in-IDs sind Konfigurationsfehler. Ohne
Konfiguration bleibt das bisherige Built-in-Verhalten unverändert. Wenn beide
Quellen angeboten werden, bleibt die Duplicate-ID-Prüfung fail-fast.

Die Exclusion aktiviert kein installiertes Modul. Nach dem Installieren bleibt das
Paket disabled, sein Runtime-Pfad fehlt, seine Migrationsquelle bleibt jedoch über
das Lockfile passiv verfügbar. Disable aktiviert den Built-in nicht wieder.

## Folgen

Der Cutover ist Deployment-/Build-Konfiguration und führt weder Resolver noch
Registry-Download, Trust-State oder Hot Reload ein. Historische Migrationen dürfen
nur nach bytegenauer Prüfung des gepinnten Modulartefakts exklusiv an dieses
übergeben werden. Parallel vorhandene Revisionen bleiben ein Fehler; Revision IDs
und Kanten werden nie umgeschrieben.
