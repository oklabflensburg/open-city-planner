# OCP Package Bundle v1

Das `.ocp`-Bundle ist das öffentliche, passive Release- und Transportformat für
genau ein separat verteiltes Modulrelease. Es ist weder Installer noch Runtime:

```text
lokale .ocp-Datei
  -> sicherer Bundle-Reader
  -> VerifiedModulePackage
  -> bestehender ModuleInstaller
  -> modules.lock
```

## Format und Struktur

Version 1 verwendet ZIP mit der Dateiendung `.ocp`. Der empfohlene Dateiname ist
`<module-id>-<version>.ocp`; die Identität wird jedoch ausschließlich aus dem
validierten Inhalt abgeleitet.

```text
energy-analysis-1.4.0.ocp
├── module.yaml
├── backend/
│   └── ocp_module_energy_analysis-1.4.0-py3-none-any.whl
├── frontend/
│   └── energy-analysis-1.4.0.tgz
└── checksums.json
```

Backend-only und Frontend-only lassen den jeweils anderen Ordner weg. Mindestens
eine Komponente ist Pflicht. Andere Roots, mehrere Artefakte einer Komponente und
nicht deklarierte Dateien sind unzulässig.

## `module.yaml`

`module.yaml` ist ein strikt validierter Distribution-Wrapper:

```yaml
bundle_format_version: 1
module_id: energy-analysis
version: 1.4.0
publisher: oklabflensburg
source:
  type: local
  reference: releases/energy-analysis-1.4.0
provenance:
  source_repository: https://github.com/oklabflensburg/ocp-module-energy-analysis
  source_commit: 0123456789abcdef0123456789abcdef01234567
  source_tag: v1.4.0
  build_workflow: github-actions/module-release
  license: AGPL-3.0-only
  sbom_reference: null
  attestation_reference: null
manifest:
  manifest_version: 1
  id: energy-analysis
  version: 1.4.0
  # übriger bestehender Manifest-V1-Contract
backend:
  artifact: backend/ocp_module_energy_analysis-1.4.0-py3-none-any.whl
frontend:
  artifact: frontend/energy-analysis-1.4.0.tgz
```

Das eingebettete bestehende Manifest bleibt Source of Truth für Compatibility,
Dependencies, Capabilities, Permissions, Config und Persistence. Die gespiegelten
Felder `module_id` und `version` müssen exakt übereinstimmen. Unbekannte
Bundle-Versionen und Felder sowie doppelte YAML-Keys werden abgelehnt. Das sichere
YAML-Laden erlaubt keine Python-Tags oder Objektkonstruktion. Publisher ist reine
Provenance, kein Trust-Grant.

## Checksums und Release-Digest

`checksums.json` enthält ausschließlich lowercase SHA-256-Digests und muss exakt
jede deklarierte Payload abdecken:

```json
{"algorithm":"sha256","files":{"backend/foo.whl":"<64 lowercase hex>"}}
```

`module.yaml` und `checksums.json` besitzen keinen rekursiven Self-Hash. Der
authoritative Release-Digest ist SHA-256 über die vollständigen `.ocp`-Bytes und
wird ohne Lockfile-Schemaänderung in `modules.lock` als `artifact.sha256`
gespeichert. Der bestehende kanonische Komponenten-Digest bleibt intern für den
`VerifiedModulePackage`-Handoff erhalten.

## Bauen, prüfen und installieren

```bash
cd backend

uv run python -m app.cli.modules bundle build \
  --manifest ../module.yaml \
  --backend ../dist/ocp_module_energy_analysis-1.4.0-py3-none-any.whl \
  --frontend ../dist/energy-analysis-1.4.0.tgz \
  --publisher oklabflensburg \
  --source-reference releases/energy-analysis-1.4.0 \
  --source-repository https://github.com/oklabflensburg/ocp-module-energy-analysis \
  --source-commit 0123456789abcdef0123456789abcdef01234567 \
  --source-tag v1.4.0 \
  --build-workflow github-actions/module-release \
  --license AGPL-3.0-only \
  --output ../dist/energy-analysis-1.4.0.ocp

uv run python -m app.cli.modules verify ../dist/energy-analysis-1.4.0.ocp
uv run python -m app.cli.modules install ../dist/energy-analysis-1.4.0.ocp
uv run python -m app.cli.modules enable energy-analysis
```

Der Builder validiert Manifest und Artefakttypen und erzeugt bei gleichen Inputs
byte-identische ZIPs: feste Reihenfolge und Zeitstempel, normalisierte Rechte und
definierte Deflate-Kompression. `verify` ist read-only; `install` übernimmt die
bestehende atomare Installer-Semantik und installiert zunächst disabled. Das
frühere `verified-package-input.json` bleibt ausschließlich ein privater Handoff
und eine Test-Fixture.

## Sicherheitsgrenzen

Der Reader extrahiert niemals pauschal. Er validiert und liest jedes Member
einzeln, verifiziert die Payload-Digests und staged nur die exakt deklarierten
Artefakte in einem automatisch bereinigten `TemporaryDirectory`. Abgelehnt werden
absolute, nicht normalisierte, Backslash-, NUL- und Traversal-Pfade, doppelte
Pfade, unbekannte Roots, Verschlüsselung, Symlinks und sonstige Spezialdateien.
Grenzen gelten für 32 Archiv-Member, 256 MiB je Datei, 512 MiB komprimierte sowie
512 MiB gesamte unkomprimierte Größe; Dateien über 1 MiB dürfen höchstens ein
Kompressionsverhältnis von 200:1 haben.

Der Reader prüft beim Wheel nur Pfad, Typ und Digest. Namespace, Distribution,
Entry Point und `--no-index --no-deps` bleiben Aufgabe des bestehenden Installers.
Entsprechend validiert dessen bestehender Frontendpfad das verschachtelte `.tgz`,
`module.json` und den realen Nuxt-Modulvertrag. Fehler verändern weder Installation
noch `modules.lock`.

## Registry-Übergabe

Eine spätere Registry (#175) kann ID, Version, Publisher, Lizenz, lokale/remote
Artefaktadresse, vollständigen Bundle-SHA-256 und Compatibility-Zusammenfassung
indexieren. Version 1 implementiert weder Netzwerkzugriff noch Registry,
Signatur-PKI, Runtime-Download, Upgrade oder Uninstall.
