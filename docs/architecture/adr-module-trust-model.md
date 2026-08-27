# ADR: Trust- und Sicherheitsmodell für Module

Status: Accepted

Datum: 2026-08-27

Issue: #109

Epic: #91

## Kontext

Open City Planner ist ein modularer Monolith. Backend-Module werden als Python-Code
in den FastAPI-Prozess importiert; Frontend-Module werden in denselben Nuxt-Build
und Browser-Kontext wie der Host aufgenommen. Die vorhandenen Manifeste,
Capabilities, Permissions, Registries und Context-Ports strukturieren diese
Zusammenarbeit, erzeugen aber keine Sicherheitsisolation.

Ein kompromittiertes In-Process-Modul kann abhängig von den Rechten des
Hostprozesses Anwendungscode und Requests beeinflussen, Daten lesen oder verändern,
Secrets aus dem Prozess lesen, Dateien öffnen, Bibliotheken importieren und
Netzwerkrequests senden. Im Browser kann Modulcode auf Browser-APIs, DOM, Host-UI
und alle im selben JavaScript-Kontext erreichbaren Daten zugreifen.

Die zentrale Sicherheitsannahme lautet deshalb:

> In-process module == trusted code. Die Modularchitektur ist keine Sandbox.

## Entscheidung

Wir unterscheiden drei Trust-Klassen. Nur die ersten beiden dürfen In-Process-Code
liefern. Der Host beziehungsweise der geprüfte Installations- und Deploymentkontext
entscheidet autoritativ über Trust. Ein Modulmanifest darf seinen Trust-Level nicht
selbst festlegen; Manifest V1 lehnt unbekannte Felder wie `trust_class` weiterhin
fail-closed ab.

### 1. First-Party Trusted

Code liegt im Hauptrepository oder wird unmittelbar vom Open-City-Planner-Team
gepflegt. Backend-Code läuft mit denselben OS-, Datenbank- und Netzwerkrechten wie
FastAPI; Frontend-Code läuft im Host-Bundle. Er durchläuft die normalen Repository-
Reviews sowie Backend-, Frontend-, E2E-, Security-, Supply-Chain- und Module-
Contract-Gates.

First-Party bedeutet organisatorisch vollständig vertraut und geprüft. Es bedeutet
nicht technisch isoliert. Der Host klassifiziert aktuell `analysis-areas` und das
Backend-`reference`-Modul anhand ihrer Entry-Point-ID und der erwarteten Host-
Distribution als First-Party. Die lokalen Frontend-Module `analysis-areas`,
`reference` und `example-module` werden durch den Build-Time-Host als First-Party
klassifiziert; diese Einstufung steht nicht in ihrer selbst kontrollierten
`module.json`.

### 2. Reviewed Community Trusted

Extern entwickelter Code darf nur nach explizitem Review In-Process installiert
werden. Reviewed Community Trusted ist nicht sandboxed. Nach der Installation kann
Python-Code technisch alles tun, was die Prozessrechte zulassen; Frontend-Code hat
Zugriff auf den gemeinsamen Browser-Kontext.

Vor dem Import eines Community-Entry-Points verlangt die Host-Discovery einen
hostseitigen Trust-Grant. Dieser bindet mindestens Modul-ID und -Version,
Distribution und exakte Paketversion, HTTPS-Quelle, vollständigen Commit-SHA,
SHA-256-Integrität, Lizenz, Review-Zeitpunkt und verantwortliche Review-Identität.
Distribution und Paketversion werden vor dem Import geprüft; Modul-ID und
Manifestversion werden danach vor der Runtime-Instanziierung gebunden. Ohne Grant,
bei unbekannter Integrität oder bei einer Abweichung bleibt das Modul blockiert.

Der Installationsreview umfasst mindestens:

- Herkunft, Repository, Maintainer, Version, Commit und Paketintegrität;
- Lizenz, direkte und transitive Dependencies sowie Lockfile;
- Manifest, Capabilities, Permissions und Service-/Event-Verträge;
- Settings, Secrets und dokumentierte externe Endpunkte;
- Dateisystem- und Netzwerkzugriffe einschließlich Telemetrie;
- Persistence-Ownership und jede Migration;
- Jobs, Lifecycle-Hooks und Incident-/Disable-Verhalten;
- Frontend-Contributions, Browser-Zugriffe und Build-Auswirkungen;
- SBOM, bekannte Schwachstellen, Secret Scan und SAST-Ergebnisse.

Ein beispielhafter hostseitiger Datensatz lautet:

```json
{
  "module": "example-community-module",
  "module_version": "1.2.3",
  "package": "example-community-module",
  "package_version": "1.2.3",
  "source": "https://github.com/example/community-module",
  "commit": "0123456789abcdef0123456789abcdef01234567",
  "reviewed_at": "2026-08-27T09:00:00Z",
  "reviewed_by": "security-review@example.org",
  "integrity": "sha256:<64 lowercase hex>",
  "license": "AGPL-3.0-only",
  "trust_class": "reviewed-community"
}
```

Die Runtime stellt bewusst keine öffentliche Installation beliebiger Module bereit.
Die produktive Composition Root konfiguriert derzeit keine Community-Grants. Ein
späterer Installationsweg muss solche Datensätze außerhalb des fremden Pakets,
reviewbar und deploy-time kontrolliert persistieren.

### 3. Remote / Untrusted Integration

Nicht vertrauenswürdiger Code läuft außerhalb von FastAPI, Nuxt und den
Hintergrundprozessen. Remote Integrations sind keine normalen In-Process-Module und
erhalten keinen `ModuleContext`, keine PostgreSQL- oder Redis-Credentials, keine
Host-Secrets, keinen Dateisystemzugriff und keinen Zugriff auf In-Process-Registries.

Kommunikation erfolgt ausschließlich über explizite stabile Verträge wie HTTP,
OGC API, WMS/WFS, Vector Tiles, GeoJSON, Webhooks, Event APIs oder Remote Data
Feeds. Jeder konkrete Adapter muss die vorhandenen HTTP- und Observability-Helfer
verwenden und mindestens folgende Schutzmaßnahmen definieren und testen:

- explizite Zielhost-/Origin-Allowlist und SSRF-sichere DNS-/IP-Prüfung;
- TLS-Verifikation und eng begrenzte, getrennte Authentifizierung;
- Connect-/Read-/Gesamttimeouts, Connection Limits und Rate Limits;
- Request- und Response-Payload-Limits sowie Content-Type-Validierung;
- begrenzte Retries mit Backoff/Jitter und Circuit-Breaking-Verhalten;
- deaktivierte Redirects oder erneute Prüfung jedes Redirect-Ziels;
- strukturierte, datensparsame Logs, Metriken und Traces ohne Credentials/PII.

Diese ADR führt weder Service Mesh noch Microservice-Plattform ein. Bestehende
Integrationen werden bei ihrer nächsten fachlichen Änderung gegen diese Checkliste
bewertet.

## Capabilities und Permissions

Capabilities beschreiben auditierbar, welche technischen Fähigkeiten ein Modul
anbietet oder benötigt. Permissions beschreiben durch den Host ausgewertete
Benutzerrechte. Beide unterstützen Architektur, Kompatibilität, UI, Review und
Dokumentation. Capability-/Permission-Enforcement ist keine OS- oder
Prozessisolation: Trusted Python-Code könnte diese offiziellen APIs technisch
umgehen. Sicherheitsentscheidungen an HTTP-/Daten-Grenzen bleiben serverseitig.

## Secrets und Konfiguration

Der unterstützte Weg ist ausschließlich das namespacete
`ModuleContext.settings` mit `OCP_MODULE_<MODULE-ID>_...` und expliziten
`SecretStr`-/`SecretBytes`-Feldern. Module dürfen offiziell weder `os.environ`
durchsuchen, `.env` selbst lesen noch globale Host-Settings importieren. Der
Architecture-Check blockiert neue direkte Environment-Loader im Hauptrepository,
soweit statisch erkennbar.

Dies verhindert versehentliche Grenzverletzungen, ist aber keine Sandbox: bereits
vertrauter Python-Code kann technisch weiterhin Prozessumgebung oder Speicher
lesen. Secret-Werte erscheinen nicht im Modul-Inventar, in Logs, Metriklabels oder
Traces.

## Datenbank und Migrationen

Module teilen den Host-Connection-Pool. Schema-, Tabellen- und Metadata-Ownership
ist eine Architekturgrenze, keine PostgreSQL-Sandbox zwischen In-Process-Modulen.
Der offizielle Zugriff erfolgt über `ModuleContext.database` und eigene
Repositories. Architecture Tests blockieren direkte Host-DB- und fremde
Modulimporte im Repository.

First-Party-Migrationen folgen der bestehenden Modul-Migrationspolicy. Bei Reviewed
Community werden alle Revisionen vor Installation geprüft. Runtime-DDL, stille
Migrationen und Änderungen an fremden Tabellen sind unzulässig. Eine ausdrücklich
genehmigte Host-/Cross-Module-Migration benötigt ein eigenes Review. Deaktivierung
oder Entfernung löscht keine Daten und führt keinen automatischen Downgrade aus.

## Netzwerk

First-Party-Code folgt den normalen Projektregeln und verwendet vorhandene
instrumentierte Clients. Reviewed-Community-Code deklariert im Review sämtliche
externen Hosts, Endpoints, Settings, Credentials, Payloads und Retrypfade. Verdeckte
Telemetrie oder Trackingziele sind unzulässig. Eine Capability-Liste ist keine
Netzwerk-Sandbox; technische Egress-Isolation würde einen getrennten Prozess oder
eine Infrastrukturgrenze erfordern.

## Frontend

Frontend-Contributions werden build-time aus lokalen, host-kontrollierten
Verzeichnissen aufgenommen. Sie dürfen deklarativ eingeschränkte Contributions
liefern, laufen zur Laufzeit aber im selben Browser-Bundle. Reviewed Community
Frontend-Code ist deshalb ebenfalls Trusted Code. Untrusted UI darf künftig nur
über eine separate Origin und eine eng konfigurierte Isolation wie ein sandboxed
iframe geprüft werden; dies ist nicht Bestandteil dieses Issues.

## Supply Chain und Integrität

Für First-Party und Reviewed Community gelten exakte Dependency-Versionen,
gelockte transitive Dependencies, Lizenzsichtbarkeit, bekannte-Schwachstellen-
Scans, Secret Scan, CodeQL/SAST und CycloneDX-SBOM. Community-Artefakte benötigen
zusätzlich nachvollziehbare Source Provenance, vollständigen Commit-SHA und
SHA-256-Checksumme/Package-Integrity.

Signaturen werden heute nicht als eigene PKI eingeführt: Das Projekt veröffentlicht
noch kein eigenständiges signiertes Modul-Artefakt und besitzt keinen belastbaren
Key-Lifecycle. Entscheidung: checksums/provenance now, signing deferred. Sobald
separate Modul-Artefakte oder ein Distributionskanal existieren, müssen Sigstore-
Attestations oder eine gleichwertige Signatur samt Schlüssel-/Identitätsrotation in
einem Follow-up bewertet werden.

## Operationales Inventar und Observability

Das stabile Build-Kompatibilitätsinventar bleibt absichtlich bei ID und Version.
Ein getrenntes operationales Statusinventar liefert ohne Secrets ID, Version,
hostbestimmte Trust-Klasse, Capabilities und Provenance. Es ist die Datenbasis für
eine spätere Admin-Statusansicht aus #111 und bläht den Frontend-Build-Contract
nicht auf. Runtime-Logs enthalten zusätzlich `module_trust_class`.

## Incident Response und Disable

Bei einer Schwachstelle wird zuerst der hostseitige Grant beziehungsweise die
Enablement-Konfiguration entzogen und ein neuer geprüfter Release gebaut:

```text
Vulnerability oder kompromittierte Quelle
  -> Installation/Update blockieren
  -> Modul aus ENABLED_MODULES und OCP_FRONTEND_MODULES entfernen
  -> Backend/Frontend neu bauen und deployen
  -> keine Router, Jobs, Lifecycle- oder UI-Contributions registrieren
  -> Ursache und betroffene Version in Adminstatus/Logs dokumentieren
  -> Daten und Migrationshistorie erhalten
```

Critical blockiert beziehungsweise deaktiviert standardmäßig. High verlangt ein
explizites Security-Review nach `SECURITY.md`. Eine kompromittierte Quelle oder
unbekannte Integrität blockiert Installation und Update. Security-Ausnahmen folgen
ausschließlich dem befristeten, reviewpflichtigen Repository-Prozess.

## Konsequenzen

- Trust ist explizit und vom Modulmanifest unabhängig.
- Community-Code kann nicht durch bloßes Installieren/Aktivieren importiert werden.
- Bestehende SDK-Primitives bleiben die offiziellen Architekturgrenzen.
- Es gibt bewusst kein Versprechen technischer Isolation für In-Process-Code.
- Operationales Inventar und Logs machen Trust und Capabilities auditierbar.
- Echte Isolation erfordert Remote Contracts beziehungsweise getrennte Prozesse.

## Abgelehnte Alternativen

### Python-In-Process-Sandbox

Abgelehnt, weil sie im Hostprozess keine belastbare Sicherheitsgrenze bietet.

### Beliebige Runtime-Plugins

Remote-Download, `pip install <URL>`, `npm install <Paket>`, Remote-Python-Import
und One-Click-Installation ungeprüften Codes sind abgelehnt.

### Microservice Big Bang

Ein eigener Service pro Modul ist nicht Ziel des modularen Monolithen. Remote
Integrationen bleiben die gezielte Grenze für untrusted/externe Fälle.

### Trust im Manifest

Abgelehnt, weil ein fremdes Modul sich sonst selbst als First-Party deklarieren
könnte. Das Manifest beschreibt Anforderungen und Contributions; Autorisierung
gehört dem Host-/Deploymentkontext.
