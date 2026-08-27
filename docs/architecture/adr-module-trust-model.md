# ADR: Trust- und Sicherheitsmodell für Module

Status: Accepted

Datum: 2026-08-27

Issue: #109

Epic: #91

## Kontext

Open City Planner ist ein modularer Monolith. Backend-Module laufen im FastAPI-
Prozess; Frontend-Module werden in den Nuxt-Build und denselben Browser-Kontext wie
der Host aufgenommen. Manifeste, Capabilities, Permissions, Registries und
`ModuleContext` strukturieren die Zusammenarbeit, erzeugen aber keine technische
Isolation.

> In-process modules are trusted code. The module architecture is not a sandbox.

> Installation, source provenance, integrity and review of Third-Party modules are
> deployment concerns handled outside the runtime. See #173 and #174.

Ein kompromittiertes In-Process-Modul kann grundsätzlich alles tun, was die Rechte
des Hostprozesses beziehungsweise der gemeinsame Browser-Kontext erlauben. Deshalb
wird fremder Code nicht erst in der Discovery oder Runtime vertrauenswürdig.

## Entscheidung

Wir unterscheiden drei organisatorische Trust-Klassen. Sie sind Policy für Review,
Installation und Deployment; sie werden nicht als zusätzliche Runtime-Hierarchie
modelliert. Die Runtime bleibt bei `ModuleDefinition`, aktivierten IDs und
installierten Python-Entry-Points.

### 1. Built-in / First-Party

Code im Hauptrepository und in den gemeinsam gebauten Host-Artefakten ist inhärent
First-Party. Dazu gehören die eingebauten Backend- und Frontend-Module. Er durchläuft
die normalen Repository-Reviews sowie Backend-, Frontend-, E2E-, Security-, Supply-
Chain- und Module-Contract-Gates. Die Runtime muss ihn weder nochmals klassifizieren
noch anhand von Paketnamen autorisieren.

First-Party bedeutet organisatorisch vertraut und geprüft, nicht technisch isoliert.

### 2. Installed / Reviewed Third-Party

Extern entwickelter In-Process-Code darf nur durch einen kontrollierten Installer-
und Deploymentpfad in die ausführbaren Host-Artefakte gelangen. Vor der Installation
werden mindestens Herkunft, Maintainer, exakte Versionen, Commit, Integrität,
Lizenz, Dependencies, SBOM, bekannte Schwachstellen, Settings, Netzwerkzugriffe,
Permissions, Persistence und Migrationen geprüft.

Der [Installer aus #173](../modules/installer.md) hält die freigegebene Auflösung in
`modules.lock` fest. Das geplante OCP Bundle aus #174 definiert das überprüfbare
Artefaktformat. Die Pipeline lautet:

```text
Package
  -> Installer
  -> Verify/Review
  -> modules.lock
  -> Backend/Frontend artifacts installed
  -> Discovery
  -> Runtime
```

Discovery liest ausschließlich bereits installierte Distributionen. Sie ist weder
Installer noch Review-Gate und führt keine eigene Trust-Datenbank. Nach erfolgreicher
Installation läuft Third-Party-Code mit denselben Prozessrechten wie First-Party-
Code und ist daher ebenfalls Trusted Code.

### 3. Remote / Untrusted

Nicht vertrauenswürdiger Code läuft außerhalb von FastAPI, Nuxt und den
Hintergrundprozessen. Remote Integrations sind keine normalen In-Process-Module und
erhalten keinen `ModuleContext`, keine Datenbank-/Redis-Credentials, keine
Host-Secrets und keinen Zugriff auf In-Process-Registries.

Kommunikation erfolgt über explizite stabile Verträge wie HTTP, OGC API, WMS/WFS,
Vector Tiles, GeoJSON, Webhooks oder Event APIs. Konkrete Adapter benötigen:

- Zielhost-/Origin-Allowlist und SSRF-sichere DNS-/IP-Prüfung;
- TLS-Verifikation und eng begrenzte Authentifizierung;
- Connect-, Read- und Gesamttimeouts, Limits und Rate Limits;
- Payload-Limits und Content-Type-Validierung;
- begrenzte Retries mit Backoff/Jitter;
- deaktivierte Redirects oder erneute Zielprüfung;
- datensparsame Logs, Metriken und Traces ohne Credentials oder PII.

## Capabilities und Permissions

Capabilities beschreiben technische Fähigkeiten; Permissions beschreiben durch den
Host ausgewertete Benutzerrechte. Beide sind Architektur-, Kompatibilitäts- und
Reviewverträge. Sie sind keine OS- oder Prozessisolation. Sicherheitsentscheidungen
an HTTP- und Datengrenzen bleiben serverseitig.

## Secrets und Konfiguration

Repository-Module verwenden namespacetes `ModuleContext.settings` mit
`OCP_MODULE_<MODULE-ID>_...` und expliziten `SecretStr`-/`SecretBytes`-Feldern. Sie
dürfen nicht selbst `os.environ`, `os.getenv`, `.env` oder globale Host-Settings als
Konfigurationspfad verwenden. Der Architecture-Check erzwingt diese unterstützte
Grenze für First-Party-Code. Die Regel verhindert Architekturdrift; sie behauptet
keine Sandbox gegen bereits vertrauten Python-Code.

Secret-Werte erscheinen nicht im Modul-Inventar, in Logs, Metriklabels oder Traces.

## Datenbank und Migrationen

Module teilen den Host-Connection-Pool. Der offizielle Zugriff erfolgt über
`ModuleContext.database`, eigene Tabellen und eigene Repositories. Schema-, Tabellen-
und Metadata-Ownership ist eine Architekturgrenze, keine PostgreSQL-Sandbox.

First-Party-Migrationen folgen der bestehenden Modul-Migrationspolicy. Bei
Third-Party-Modulen werden alle Revisionen vor Installation geprüft. Runtime-DDL,
stille Migrationen und Änderungen an fremden Tabellen sind unzulässig. Eine
Deaktivierung oder Entfernung löscht keine Daten und führt keinen automatischen
Downgrade aus.

## Netzwerk und Frontend

In-Process-Code deklariert externe Hosts, Endpoints, Credentials, Payloads und
Retrypfade. Verdeckte Telemetrie ist unzulässig. Technische Egress-Isolation erfordert
einen getrennten Prozess oder eine Infrastrukturgrenze.

Frontend-Contributions werden build-time aus installierten, host-kontrollierten
Artefakten aufgenommen und laufen im gemeinsamen Browser-Bundle. Untrusted UI darf
nur über eine getrennte Origin und eine ausdrücklich geprüfte Isolation angebunden
werden; das ist nicht Bestandteil dieses Issues.

## Supply Chain und Integrität

Für In-Process-Module gelten exakte Dependency-Versionen, gelockte transitive
Dependencies, Lizenzsichtbarkeit, Schwachstellen- und Secret-Scans, CodeQL/SAST und
CycloneDX-SBOM. Third-Party-Artefakte benötigen zusätzlich nachvollziehbare Source
Provenance, vollständigen Commit-SHA und SHA-256-Integrität.

Eine eigene Signatur-PKI wird erst mit realen separaten Modul-Artefakten und einem
Distributionskanal bewertet: checksums/provenance now, signing deferred. #173 und
#174 konkretisieren diesen Installations- und Artefaktpfad.

## Inventar, Incident Response und Disable

Das technische Kompatibilitätsinventar bleibt bei Modul-ID und Version. Es gibt in
der Runtime kein paralleles operationales Trust-Inventar.

Bei einer Schwachstelle wird Installation oder Update blockiert, das Modul aus der
Build-/Deployment-Konfiguration entfernt und ein neues geprüftes Release gebaut.
Router, Jobs, Lifecycle- und UI-Contributions werden dadurch nicht registriert;
Daten und Migrationshistorie bleiben erhalten. Critical blockiert beziehungsweise
deaktiviert standardmäßig. High benötigt ein explizites Security-Review nach
`SECURITY.md`.

## Konsequenzen

- Built-ins sind inhärent First-Party.
- Third-Party-Trust wird an der Installer-/Deploymentgrenze entschieden (#173/#174).
- Discovery und Runtime bleiben klein und kennen keine Trust-Grants oder Trust-Typen.
- Die unterstützten SDK-Primitives bleiben die Architekturgrenzen.
- Echte Isolation erfordert Remote Contracts beziehungsweise getrennte Prozesse.

## Abgelehnte Alternativen

Eine Python-In-Process-Sandbox wird nicht behauptet, weil sie im Hostprozess keine
belastbare Sicherheitsgrenze bietet. Runtime-Downloads, URL-Installationen und
One-Click-Ausführung ungeprüften Codes bleiben ausgeschlossen. Ein Service pro Modul
ist nicht Ziel des modularen Monolithen; getrennte Prozesse sind die gezielte Grenze
für untrusted Integrationen.
