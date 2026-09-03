# Installer und `modules.lock`

Der Installer verwaltet separat verteilte, bereits lokal bereitgestellte Module
zwischen Package-Verifikation und dem bestehenden deploy-time Enablement. Eine
optionale Registry-Schicht löst ein Release auf und lädt dessen Bundle vollständig
und digestgeprüft in eine private temporäre Datei; ab dort bleibt derselbe lokale
Bundle-/Installer-Pfad maßgeblich. Built-ins
im Host-Repository bleiben außerhalb dieses Zustands. Das
[Manifest V1](module-manifest-v1.md) bleibt Source of Truth für fachliche Identität,
Version, Compatibility und Dependencies; `modules.lock` beschreibt ausschließlich
den reproduzierbaren Installationszustand. Der
[operationale Modulstatus](operations.md) beschreibt weiterhin nur die laufende
Runtime.

```text
Registry v1 -> private temporäre .ocp-Datei (HTTPS + SHA-256)
             \-> oder bereits lokale .ocp-Datei
  -> Bundle-Reader / VerifiedModulePackage
  -> installer
  -> modules.lock
  -> versionierte Backend-/Frontend-Artefakte
  -> generierte deploy-time Environmentwerte
  -> bestehende Discovery, Preflights und Runtime
```

Es gibt kein Hot Install oder Hot Reload. Enable und Disable werden erst durch den
nächsten Build, Deploy beziehungsweise Prozessneustart wirksam.

## Host-owned Ablage

Der Produktionsstandard ist `/var/lib/stadtplaner/modules`. Für lokale oder
isolierte Vorgänge kann `OCP_MODULE_INSTALL_ROOT` beziehungsweise die CLI-Option
`--root` einen anderen host-owned Pfad setzen.

```text
/var/lib/stadtplaner/modules/
├── modules.lock
├── .modules.lock.lock
└── installed/
    └── energy-analysis/
        └── 1.4.0/
            ├── artifacts/
            │   ├── ocp_module_energy_analysis-1.4.0-py3-none-any.whl
            │   └── energy-analysis-1.4.0.tgz
            ├── backend/site-packages/
            └── frontend-modules/energy-analysis/
                ├── module.json
                └── layer/
```

Der Installer schreibt weder nach `backend/app/modules` noch nach
`frontend/frontend-modules` und patcht keine Hostdatei. Die versionierte Ablage
bleibt auch bei Disable erhalten, damit Migrationsressourcen weiterhin passiv
auflösbar sind. Deaktivierte Backend-Pfade werden nicht in den Runtime-Importpfad
aufgenommen.

Dabei gelten drei getrennte Zustände:

```text
Installed package availability
!= Runtime import activation
!= Migration history availability
```

## Lockfile-Contract

`modules.lock` ist strict validiertes JSON mit `format_version: 1`. Unbekannte
Felder, eine unbekannte Formatversion, unsortierte oder doppelte IDs, ungültiges
SemVer, nicht boolesches Enablement, fehlende Artefaktmetadaten und ungültige
SHA-256-Werte werden fail-fast abgelehnt.

```json
{
  "format_version": 1,
  "modules": [
    {
      "id": "energy-analysis",
      "version": "1.4.0",
      "enabled": false,
      "publisher": "oklabflensburg",
      "source": {
        "type": "local",
        "reference": "reviewed/energy-analysis-1.4.0"
      },
      "provenance": {
        "source_repository": "https://github.com/oklabflensburg/ocp-module-energy-analysis",
        "source_commit": "0123456789abcdef0123456789abcdef01234567",
        "source_tag": "v1.4.0",
        "build_workflow": "github-actions/module-release",
        "license": "AGPL-3.0-only",
        "sbom_reference": null,
        "attestation_reference": null
      },
      "artifact": {
        "identifier": "energy-analysis-1.4.0",
        "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
      },
      "backend": {
        "present": true,
        "artifact": "ocp_module_energy_analysis-1.4.0-py3-none-any.whl",
        "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
      },
      "frontend": {
        "present": true,
        "artifact": "energy-analysis-1.4.0.tgz",
        "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
      }
    }
  ]
}
```

Einträge sind nach kanonischer Modul-ID sortiert. Keys besitzen stabile Reihenfolge,
Digests sind lowercase SHA-256, volatile Zeitstempel fehlen und die Datei endet mit
genau einem Newline. Änderungen werden unter einem lokalen File Lock in eine
temporäre Datei geschrieben, mit `fsync` gesichert und über `os.replace()` atomar
aktiviert. Der Installer ist ein serialisierter Deploymentvorgang; eine verteilte
Lock-Infrastruktur existiert nicht.

Das Lockfile enthält keine Secrets, Prozessgesundheit, laufende Hooks oder andere
Runtime-Fakten. `backend/uv.lock` und `frontend/pnpm-lock.yaml` bleiben davon
getrennte Host-Dependency-Locks.

## Interner Package-Input

`VerifiedModulePackage` ist der schmale interne Übergabevertrag des Installers. Er
enthält Modul-ID und Version, Publisher und Source, Release- und
Komponenten-Digests, Source Repository und vollständigen Commit, Build Workflow,
Lizenz sowie optionale Tag-, SBOM- und Attestation-Referenzen. Hinzu kommen
Backend-/Frontend-Artefaktbeschreibungen und der bestehende Manifestinhalt. Der
Vertrag ist kein neues fachliches Manifest.

Der öffentliche Nutzerpfad ist das [`.ocp` Package Bundle v1](package-bundle.md).
Der sichere Bundle-Reader erzeugt nach Struktur-, Manifest- und Digestprüfung genau
denselben `VerifiedModulePackage`, den der bestehende Installer konsumiert. Das
Verzeichnis mit `verified-package-input.json` und referenzierten lokalen Artefakten
bleibt ein privater Handoff und eine interne Test-Fixture.

Der Release-Digest bindet deterministisch Identifier und SHA-256 der vorhandenen
Backend-/Frontend-Artefakte. Jeder Komponenten-Digest wird zusätzlich gegen die
tatsächlichen Bytes geprüft. Package-ID und -Version müssen mit dem vorhandenen
Backend-Manifest, dem Wheel-Entry-Point und `frontend/module.json` übereinstimmen.
Vor dem Commit der Installation prüft `pnpm modules:check` das ausgepackte
Frontend-Artefakt mit dem realen bestehenden Frontend-Contract, auch wenn das Modul
zunächst disabled bleibt.

## Sicherheitsgrenzen

Vor einer Änderung des Installationszustands gelten folgende Regeln:

- nur bereits lokale Artefakte; `uv pip install` läuft mit `--no-index --no-deps`;
- keine Package-Shellhooks, Post-Install-Skripte oder Befehle aus Metadaten;
- ausschließlich normalisierte relative POSIX-Pfade;
- keine absoluten Pfade, `..`, NUL-Zeichen oder Backslash-Pfade;
- keine Symlinks oder Hardlinks in Packagepfaden und Frontend-Archiven;
- keine doppelten Archivpfade, Devices oder sonstigen Spezialdateien;
- Backend-Wheels dürfen auf Top-Level ausschließlich ihr kanonisches
  `ocp_module_<module_id>`-Package und das zugehörige `.dist-info` enthalten;
- kein Überschreiben einer anderen Modul-ID oder eines vorhandenen Releases;
- keine Priorität zwischen Built-in und Installed bei gleicher ID.

Bei Digest-, ID-, Versions-, Pfad- oder Strukturfehlern bleiben Lockfile und
Zielinstallation unverändert. Dieselbe ID, Version und derselbe Digest sind
idempotent. Eine andere Version oder ein anderer Digest benötigt einen später
explizit definierten Upgradepfad.

## CLI

Die CLI folgt den bestehenden Python-Modulbefehlen:

```bash
cd backend

uv run python -m app.cli.modules --root /var/lib/stadtplaner/modules \
  verify /srv/reviewed/energy-analysis-1.4.0.ocp

uv run python -m app.cli.modules --root /var/lib/stadtplaner/modules \
  install /srv/reviewed/energy-analysis-1.4.0.ocp

uv run python -m app.cli.modules --root /var/lib/stadtplaner/modules \
  install-registry analysis-areas --channel stable

uv run python -m app.cli.modules --root /var/lib/stadtplaner/modules \
  install-registry analysis-areas --version 1.5.2 \
  --expected-sha256 835a2745da15cdc17587324e451ea1b922ae0628738603c7a061d62407d08d58

uv run python -m app.cli.modules --root /var/lib/stadtplaner/modules \
  enable energy-analysis

uv run python -m app.cli.modules --root /var/lib/stadtplaner/modules \
  disable energy-analysis

uv run python -m app.cli.modules --root /var/lib/stadtplaner/modules \
  list --format json

uv run python -m app.cli.modules --root /var/lib/stadtplaner/modules \
  env --format shell
```

Der konkrete Analysis-Areas-Pin `1.5.2` dient hier ausschließlich als
Beispiel für den produktiven, digest-gepinnten Registry-Pfad. Der vollständige
Installations-, Enable-/Disable-/Re-enable- und Runtime-Nachweis steht im
[Cutover-Bericht zu v1.5.2](analysis-areas-cutover-v1.5.2.md).

`verify` verändert nichts. `install` verifiziert und installiert atomar und setzt
`enabled: false`. `enable` prüft erneut die gespeicherten Artefakte und führt die
bestehenden Manifest-, Host-/SDK-, Dependency-, Settings-, Migrations- und
Frontend-Preflights aus. Erst danach wird `enabled: true` atomar gespeichert.
`disable` ist idempotent, ändert nur das Enablement und führt weder Migration,
Downgrade, Datenlöschung noch Artefaktentfernung aus.

`list` liefert Built-ins und installierte Module in getrennten `kind`-Werten. Die
Installationssicht enthält keine laufenden Runtime-Zustände. `env` rendert die
authoritative installierte Enablement-Entscheidung in die bestehenden
Deploymentverträge:

```text
ENABLED_MODULES
OCP_FRONTEND_MODULES
OCP_BACKEND_MODULES
OCP_ENABLED_INSTALLED_BACKEND_PATHS
OCP_INSTALLED_FRONTEND_MODULE_ROOTS
OCP_EXCLUDED_BUILTIN_MODULES
```

`OCP_ENABLED_INSTALLED_BACKEND_PATHS` enthält ausschließlich Backend-Pfade der
installierten Module mit `enabled: true`. Die Runtime hängt sie nach Host-Code und
Venv-Dependencies an ihren Prozesspfad an. Deaktivierte Pakete können dadurch keine
Host- oder Dependency-Imports shadowen. Der Migrations-CLI liest dagegen alle
installierten Backend-Pfade direkt aus `modules.lock` und aktiviert sie nur scoped
für passive Discovery, Preflight und Upgrade. Es gibt keine zweite manuell gepflegte
Migration-Path-Variable. Built-ins werden weiterhin über die bestehende
Hostkonfiguration ergänzt und niemals in `modules.lock` geschrieben.

### Installation aus Registry v1

`install-registry` ist bewusst nur eine dünne Eingabeschicht vor `install`. Der
Default ist `https://packages.stadtplaner.oklabflensburg.de`; `--registry-url`
überschreibt ihn, alternativ setzt `OCP_MODULE_REGISTRY_URL` einen nicht geheimen
Deploymentwert. Ohne `--version` oder `--channel` wird `stable` aufgelöst. Beide
Optionen schließen einander aus. Für reproduzierbare Deployments ist immer die
exakte Version zusammen mit `--expected-sha256` zu verwenden; der Pin muss sowohl
zum Registry-Index als auch zu den Modulmetadaten und den empfangenen Bytes passen.

Index und Modulmetadaten werden strikt als Schema v1 validiert. Unbekannte Felder,
IDs, Versionen, Channels und Schema-Versionen sowie widersprüchliche ID-, Publisher-,
Klassifikations-, Channel-, Bundleformat- oder Digestangaben werden abgelehnt.
Metadata-Referenzen müssen sichere `/modules/*.json`-Pfade auf demselben Registry-
Origin sein. Artefakte werden nur von einem kanonischen versionierten Registry-Pfad
oder einem versionierten GitHub Release akzeptiert.

Alle Netzwerkziele müssen HTTPS ohne eingebettete Zugangsdaten verwenden. Der Client
setzt getrennte Connect-/Read-Timeouts, folgt höchstens fünf Redirects und prüft nach
jedem Redirect erneut das Schema. Registry-Dokumente sind auf 1 MiB und Bundles auf
512 MiB begrenzt. Bundlebytes werden gestreamt, während des Empfangs gehasht und in
einer privaten temporären Datei gehalten; `Content-Length`, Größenlimit und SHA-256
werden vor dem Bundle-Reader geprüft. Temporäre Daten werden bei Erfolg und Fehler
entfernt.

Ein Fehler verändert weder `installed/` noch `modules.lock`. Die Registry wird nur
durch diesen expliziten CLI-Befehl kontaktiert: API-, Worker-, Migrations- und
Application-Startup, Builds sowie bereits installierte Module bleiben vollständig
offlinefähig. Es gibt keine Updateprüfung, transitive Installation oder Ausführung
von Registry-Metadaten. Eine Erstinstallation bleibt deaktiviert und benötigt
weiterhin einen separaten `enable`- und Deploy-Schritt.

`OCP_EXCLUDED_BUILTIN_MODULES` ist der gemeinsame Backend-/Frontend-Contract für
einen kontrollierten Source-Cutover. Details stehen im
[Built-in-Cutover-Runbook](builtin-cutover.md).

## Compatibility und Lifecycle

Installieren bedeutet „lokal vorhanden“, nicht „aktuell lauffähig“. Deshalb darf
beispielsweise ein Modul für eine zukünftige Hostversion als disabled installiert
werden. Enable schlägt dagegen fehl, solange Host, SDK, Dependencies, Settings,
Migrationen oder Frontend-Contract nicht kompatibel sind. Die bestehenden
Validatoren und Preflights bleiben dafür maßgeblich; der Installer enthält keine
zweite Compatibility- oder Dependency-Engine.

Packaged First-Party und Reviewed Community verwenden exakt denselben technischen
Pfad. Publisher-, Source- und Review-Metadaten unterscheiden die Herkunft, erzeugen
aber keine Runtime-Trust-Grants. Private Module können über denselben lokalen Input
aus privatem Artifact Storage oder einem kontrollierten privaten Release
bereitgestellt werden. Eine öffentliche Registry ist nicht erforderlich.

## Runbook

### Install

1. Das bereits geprüfte lokale Package wird bereitgestellt.
2. `verify` bestätigt Digests, Identität und statische Struktur.
3. `install` erzeugt die versionierte Ablage und ersetzt `modules.lock` atomar.
4. `list` bestätigt `kind: installed` und `enabled: false`.

### Enable

1. Erneute Artefaktprüfung und alle Compatibility-/Settings-Preflights laufen.
2. Der Migrations-Preflight prüft den weiterhin vollständigen installierten Graphen.
3. Der Frontend-Preflight prüft Layer, Routes, UI und Map Contributions.
4. `enabled: true` wird gespeichert.
5. `env --format shell` speist den nächsten Build beziehungsweise Deploy.
6. Nach Neustart wird der operationale Status geprüft.

### Disable

1. `disable` setzt ausschließlich `enabled: false`.
2. Der gerenderte Build-/Deployzustand wird aktiviert.
3. Nach Build, Deploy beziehungsweise Neustart fehlen Runtime- und
   Frontend-Contributions sowie der installierte Backend-Pfad im neuen Prozess.
4. Package, Daten und Migrationsressourcen bleiben erhalten; es gibt keinen
   automatischen Downgrade.

### Rollback

Der vorherige Lock-/Artefaktzustand benennt Version und Digest reproduzierbar. Vor
einer Wiederherstellung muss die DB-Kompatibilität mit der vorherigen Modulversion
geprüft werden. Package-Rollback ist kein DB-Downgrade; ein Datenbank-Downgrade
bleibt eine separate, explizite und backupgestützte Operation.

## Bewusster Scope

Uninstall und Upgrade bleiben zunächst außerhalb von #173, weil angewandte
Migrationshistorie und DB-Kompatibilität keine sichere automatische Entfernung oder
Rücksetzung erlauben. Ebenfalls nicht enthalten sind Marketplace, Web-UI, Hot Update,
Signatur-PKI, Trust State Machine, Dependency Resolver und automatischer
DB-Downgrade.
