# Distribution Policy für installierbare Module

Diese Policy definiert die verbindlichen Namen, Release-Metadaten und
Artefaktklassen für zukünftig installierbare Open-City-Planner-Module. Sie baut auf
dem bestehenden [Manifest V1](module-manifest-v1.md), der
[Backend-Entry-Point-Discovery](backend-module-runtime.md), dem
[Frontend-Host](frontend-host.md) und dem
[Trust-Modell](../architecture/adr-module-trust-model.md) auf. Diese bestehenden
Verträge bleiben maßgeblich.

Die Policy ist der fachliche Input für den [Installer und `modules.lock`](installer.md),
das konkrete [`.ocp` Package Bundle v1](package-bundle.md) und die Registry aus
#175. Der Installer bleibt ein separater technischer Layer.

## Kanonische Identität und Namen

Die kanonische Modul-ID ist die einzige stabile Identität eines Moduls. Sie ist
lowercase ASCII in Kebab Case, beginnt mit einem Buchstaben, erfüllt
`^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$` und ist höchstens 63 Zeichen lang. Dieselbe ID
gilt über Backend, Frontend, Manifest, Bundle, Registry, Installer und späteres
Lockfile hinweg.

Für die Beispiel-ID `energy-analysis` gelten folgende Namen:

| Gegenstand | Verbindliche oder bevorzugte Form |
| --- | --- |
| kanonische Modul-ID | `energy-analysis` |
| Python-Distribution | `ocp-module-energy-analysis` |
| Python-Import-Paket | `ocp_module_energy_analysis` |
| Python-Entry-Point-Name | `energy-analysis` |
| bevorzugtes First-Party-Frontend-Paket | `@open-city-planner/energy-analysis` |
| OCP-Bundle | `energy-analysis-1.4.0.ocp` |

Der Name eines Python-Wheels kann nach der üblichen Wheel-Normalisierung zum
Beispiel `ocp_module_energy_analysis-1.4.0-...whl` lauten. Das ändert weder den
Python-Distributionsnamen noch die Modul-ID.

Community-Publisher dürfen einen eigenen npm-Scope verwenden, beispielsweise
`@publisher/ocp-module-example` für ein Modul mit `id: example`. Paket- und
Publisher-Namen sind Transportnamen. Die Runtime leitet aus ihnen niemals die
Modul-ID ab. Maßgeblich sind der
Entry-Point-Name und die ID im validierten Manifest; beide müssen übereinstimmen.
Der Scope `@open-city-planner` ist keine technische Voraussetzung für
Community-Module.

## Eine Version pro Modulrelease

Ein Modulrelease besitzt genau eine fachliche, vollständige SemVer-Version. Für
`energy-analysis` in Version `1.4.0` tragen Manifest, Backend-Wheel,
Frontend-Artefakt und Bundle dieselbe Version:

```text
Manifest:           version: 1.4.0
Backend-Wheel:      ocp_module_energy_analysis-1.4.0-...whl
Frontend-Artefakt:  energy-analysis-1.4.0.tgz
Bundle:             energy-analysis-1.4.0.ocp
```

Bei einem Fullstack-Modul bilden Backend und Frontend eine logische Releaseeinheit
und werden nicht unabhängig versioniert. Das Frontend-`module.json`, das
Backend-Manifest und die Artefaktmetadaten tragen dieselbe Modulversion.
Backend-only- und Frontend-only-Module bleiben möglich; bei ihnen fehlt die jeweils
nicht benötigte Artefaktklasse.

### SemVer-Regeln

- **PATCH** umfasst Bugfixes und interne Änderungen ohne Bruch eines öffentlichen
  Contracts. Inkompatible API-, Capability-, Settings-, Dependency- oder
  Datenänderungen sind kein Patch.
- **MINOR** umfasst additive, rückwärtskompatible Erweiterungen, zum Beispiel neue
  optionale Capabilities, APIs oder Settings sowie additive Datenbankmigrationen.
- **MAJOR** ist für inkompatible Capability- oder API-Änderungen, einen brechenden
  Settings-Contract, inkompatible Modulabhängigkeiten, einen Datencontract mit
  notwendiger brechender Migration oder die Entfernung öffentlich dokumentierter
  SDK-Nutzung erforderlich.

SemVer ersetzt kein fachliches Review. Insbesondere müssen Datenmigrationen,
Sicherheitsauswirkungen und Compatibility-Ranges unabhängig von der gewählten
Versionsstufe geprüft werden.

## Das vorhandene Manifest bleibt Source of Truth

Es entsteht kein zweites fachliches Distribution-Manifest. Das bestehende
Backend- beziehungsweise Frontend-Modulmanifest bleibt die maßgebliche Quelle für:

- ID und Version;
- Host-, SDK- und optionale Backend-Kompatibilität;
- Required und Optional Module Dependencies;
- Capabilities und Permissions;
- Config-Namespace und Persistence-Metadaten;
- Frontend-Routen sowie UI- und Map-Contributions.

Das `module.yaml` im `.ocp`-Bundle transportiert diesen Contract und ergänzt ihn
nur um Distribution-Metadaten. Gespiegelte ID, Version und
Compatibility-Metadaten müssen mit dem eingebetteten bestehenden Manifest
übereinstimmen; zwei unabhängig pflegbare Versions- oder Dependency-Modelle sind
unzulässig. Das konkrete Transportformat ist in [Package Bundle v1](package-bundle.md)
festgelegt.
Publisher-, Provenance-, Lizenz- und Digest-Angaben sind Metadaten der
Distribution, keine vom Modul selbst festgelegte Runtime-Trustklasse.

## Backend-Artefakt

Ein installierbares Backend-Modul muss als normales Python-Wheel reproduzierbar
baubar sein und mindestens Folgendes bereitstellen:

- ein `pyproject.toml` mit vollständigen Build- und Dependency-Metadaten;
- ein Wheel, das das Modul-Import-Paket und alle benötigten
  Migrationsressourcen enthält;
- einen Entry Point in der bestehenden Gruppe `open_city_planner.modules`;
- eine passive `ModuleDefinition`, deren Manifest-ID dem Entry-Point-Namen
  entspricht;
- ausschließlich Imports aus dem öffentlichen Module SDK und eigenen Paketen.

Beispiel:

```toml
[project]
name = "ocp-module-energy-analysis"
version = "1.4.0"

[project.entry-points."open_city_planner.modules"]
energy-analysis = "ocp_module_energy_analysis.module:DEFINITION"
```

Migrationen bleiben relative Ressourcen eines installierten Python-Pakets und
müssen dem bestehenden [Persistence- und Migrationsvertrag](database-and-migrations.md)
entsprechen. Nicht zulässig sind Host-interne Imports, Post-Install-Shellskripte,
Änderungen beliebiger Hostdateien und Downloads von Code oder Dependencies zur
Runtime. Wheel-Installation und Dependency-Auflösung sind Aufgaben des späteren
Installers, nicht der Discovery.

## Frontend-Artefakt

Ein installierbares Frontend-Modul muss als lokales, reproduzierbares Archiv
bereitstellbar sein. Sein ausgepackter Inhalt muss ohne Host-Patches mit dem
vorhandenen Frontend-Contract funktionieren und insbesondere enthalten:

- das deklarative `module.json`;
- den lokalen Nuxt Layer;
- alle deklarierten Pages, Components und sonstigen lokalen Quellen;
- alle deklarierten UI- und Map-Contributions.

Das Artefakt darf keine Änderungen an `app.vue`, Host-Navigation, `MapCanvas`,
Host-Pages, globalen Plugins oder anderen Hostdateien voraussetzen. Es darf keine
Runtime-Remotes oder nachgeladenen Code-Bundles verwenden. Der spätere Installer
entpackt es vor dem Nuxt-Build in die kontrollierte, versionierte Ablage aus
[#173](installer.md). Das öffentliche Archivlayout und die weitergehende
Dependency-Integration werden erst in #174 festgelegt.

## Beziehung zum OCP-Bundle v1

Ein Release `energy-analysis-1.4.0.ocp` fasst die überprüfbaren
Artefaktklassen einer Modulversion zusammen. Konzeptionell kann es enthalten:

```text
module.yaml
backend/*.whl
frontend/*.tgz
checksums.json
```

Ein Fullstack-Bundle enthält Backend und Frontend mit derselben ID und Version. Ein
Backend-only- oder Frontend-only-Bundle lässt die nicht benötigte Artefaktklasse
aus. `module.yaml` transportiert oder spiegelt den vorhandenen Manifest-Contract;
`checksums.json` bindet die enthaltenen Bytes an ihre Digests. Dateinamen,
Pflichtfelder, Checksums, Sicherheitsgrenzen, Parser und Writer beschreibt
[Package Bundle v1](package-bundle.md).

## Integrität, Provenance und Lizenz

Jedes installierbare Release benötigt einen unveränderlichen SHA-256-Digest. Für
ein Bundle ist `bundle_sha256` die primäre Referenz; zusätzliche
`backend_sha256`- und `frontend_sha256`-Werte können einzelne Artefakte binden. Die
Registry, der Installer und `modules.lock` müssen später denselben geprüften Digest
referenzieren. Eine Änderung der Bytes erzeugt einen neuen Digest und darf nicht
unter derselben aufgelösten Release-Identität still ersetzt werden.

Release-Metadaten umfassen mindestens:

- kanonische Modul-ID und Version;
- Publisher;
- Source Repository;
- vollständigen Source Commit und optional den zugehörigen Tag;
- identifizierbaren Build Workflow;
- Artefakt-Digest;
- Lizenz;
- Erstellungs- oder Releasezeitpunkt.

Eine CycloneDX-SBOM und Referenzen auf Build-Attestations sollen mitgeführt werden,
sobald die Artefaktpipeline sie erzeugt. Dafür ist die vorhandene
[Supply-Chain-Infrastruktur](../supply-chain.md) weiterzuverwenden. Eine eigene
Provenance-Plattform oder Signatur-PKI ist nicht Teil dieser Policy; gemäß
Trust-Modell gilt zunächst „checksums/provenance now, signing deferred“.

Jedes Release nennt einen SPDX-Lizenzbezeichner oder liefert einen eindeutigen
Lizenztext. Zusätzlich müssen Publisher, Source Repository, erforderliche
Copyright-/Attributionsangaben und gegebenenfalls Third-Party Notices erhalten
bleiben. Die spätere Installation darf diese Dateien und Metadaten nicht verwerfen.
Diese Mindestanforderungen sind keine juristische License-Enforcement-Engine.

## Publisher, Trustklasse und Bezugsquelle

Packaged First-Party- und Reviewed-Community-Module verwenden denselben technischen
Distribution Contract, dieselben Manifeste und dieselbe Runtime. Der Unterschied
liegt in Publisher, Source Provenance, Review und Approval an der
Installer-/Deploymentgrenze. Es entstehen weder eine `FirstPartyPackageRuntime`
noch eine `CommunityPackageRuntime`.

Die organisatorischen Fälle sind:

- **Built-in / First-Party:** liegt im Host-Repository, wird mit dem Host gebaut und
  benötigt heute weder `.ocp`, Registry, Installer noch `modules.lock`-Eintrag als
  installierte Distribution;
- **Packaged First-Party:** separates First-Party-Artefakt nach dieser Policy;
- **Reviewed Community:** separates Community-Artefakt nach demselben technischen
  Contract und dem zusätzlichen Review aus
  [Community-Modulprüfung](community-module-review.md).

Diese Unterscheidung ergänzt keine Runtime-Trustklassen. Alle aktivierten
In-Process-Module sind Trusted Code und nicht sandboxed.

Der Contract setzt keine öffentliche Registry voraus. Derselbe überprüfbare Release
kann zukünftig aus einer lokalen Datei, privatem Artifact Storage, einem privaten
GitHub Release oder einer internen Registry stammen. Die Bezugsquelle ändert weder
ID, Version, Digest noch Reviewanforderungen. Fetching und Authentifizierung dieser
Quellen gehören zum späteren Installer.

## Reproduzierbarer Installationszustand

Die Kombination aus

```text
module id + version + immutable artifact digest + publisher/source metadata
```

muss einen auflösbaren und überprüfbaren Installationszustand ergeben. Identische
Eingaben referenzieren identische Releasebytes; ein beweglicher Tag oder eine URL
allein reicht nicht aus.

`backend/uv.lock` und `frontend/pnpm-lock.yaml` bleiben Locks der
Host-Dependency-Sätze. Sie sind weder Modulinventar noch Installationsdatenbank und
dürfen dafür nicht umgedeutet werden. Der Installer aus #173 hält die freigegebene
Modulauflösung später separat in `modules.lock` fest und koordiniert dabei die
Dependency-Integration in reproduzierbare Host-Artefakte.

## Compatibility Gate vor Deployment

Distribution fügt keine neue Compatibility Engine hinzu. Der Installer und der
Deploymentpfad müssen die bereits vorhandenen Prüfungen mit den installierten
Artefakten ausführen.

Backend:

- Manifest syntaktisch gültig;
- Host- und Backend-SDK-Version kompatibel;
- Required und vorhandene Optional Module Dependencies kompatibel;
- Settings-Schema aktiver Module gültig;
- Migrationsressourcen auflösbar und Migrations-Preflight gültig.

Frontend:

- `module.json`, Host- und Frontend-SDK-Version kompatibel;
- erforderliches Backend-Modul vorhanden und versionskompatibel;
- Frontend-Modulabhängigkeiten kompatibel und azyklisch;
- Layer, Routes, UI- und Map-Contributions gültig und kollisionsfrei;
- Typecheck, SSR und gemeinsamer Nuxt-Build erfolgreich.

Das bestehende [`module-contract-gate`](module-contract-gate.md) bleibt die
gemeinsame Architekturprüfung. Security-, Supply-Chain- und manuelle
Third-Party-Reviews bleiben zusätzlich verpflichtend.

## Empfohlenes Standalone-Source-Layout

Ein separat gepflegtes Modul kann folgende Repository-Konvention verwenden:

```text
ocp-module-example/
├── module.yaml
├── backend/
│   ├── pyproject.toml
│   └── src/
│       └── ocp_module_example/
├── frontend/
│   ├── package.json
│   └── ...
├── tests/
├── LICENSE
└── README.md
```

Das Layout ist eine Source-Konvention, kein installiertes Format. `module.yaml`
bleibt dabei ein später zu definierender Transport des bestehenden Manifests.
Built-ins müssen dieses Layout nicht verwenden. Das Reference-Modul bleibt im
Host-Repository die kanonische ausführbare SDK-Dokumentation und positive
Contract-Fixture; es wird durch diese Policy weder extrahiert noch als Wheel oder
npm-Paket gebaut.

## Übergaben an Installer, Bundle und Registry

- **[#173 Installer und `modules.lock`](installer.md):** übernimmt ID, Version, Digest,
  Publisher/Source, Backend-/Frontend-Artefakte und bestehende
  Compatibility-Metadaten; definiert Installation, Ablage und persistente
  Auflösung.
- **[OCP-Bundle v1](package-bundle.md):** definiert das Archiv- und Metadatenschema,
  transportiert den bestehenden Manifest-Contract und bindet alle Artefakte per
  Digest zu einer Releaseeinheit.
- **#175 Registry:** indexiert mindestens ID, Version, Publisher, Lizenz,
  Artefakt-URL, SHA-256, Host-/SDK-Kompatibilität und Source Repository, ohne eine
  öffentliche Registry als einzige Bezugsquelle vorzuschreiben.

Nicht Teil dieser Policy sind Installer, `modules.lock`, Bundler, Bundle-Parser,
Registry, Uploads oder Downloads, Marketplace, Admin-UI, Hot Install, Hot Update,
Signatur-PKI, Trust State Machine, Modulextraktion und ein eigener Dependency
Resolver.
