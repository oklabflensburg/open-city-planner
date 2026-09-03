# Ansible Deployment

Dieses Verzeichnis automatisiert den produktiven Betrieb des Open City Planner auf dem bestehenden Shared Host. Es ersetzt bewusst nicht die globale Serververwaltung aller OK-Lab-Projekte. Nginx, PostgreSQL, Redis und Node können weitere Anwendungen bedienen; die Playbooks verändern deshalb überwiegend Stadtplaner-spezifische Dateien. Die ausdrücklich verwaltete NodeSource-22-Paketquelle und die gepinnten Corepack-/pnpm-Versionen bilden die gemeinsame JavaScript-Runtime-Ausnahme. `/etc/nginx/nginx.conf`, PostgreSQL und Redis werden nicht blind neu konfiguriert.

Der verpflichtende lokale Trace-Pfad aus OpenTelemetry Collector und Tempo wird
durch den normalen Applikationsdeploy verwaltet. Prometheus und Grafana werden
nicht durch einen normalen Applikationsdeploy verändert. Dafür existiert das separate Opt-in-Playbook
`playbooks/monitoring.yml`; die vollständige Betriebsanleitung steht unter
[`docs/monitoring-deployment.md`](../../docs/monitoring-deployment.md).

## Warum Ansible?

Für diesen Server ist ein idempotenter Deployment-Ablauf sicherer als wiederholte manuelle Änderungen: dieselben Pfade, Benutzer, systemd-Units, Builds, Migrationen, Nginx-Dateien und Smoke Tests werden bei jedem Lauf reproduzierbar angewendet. Ein normaler Deploy führt **keinen** OSM-Initialimport und **keine** Certbot-Ausstellung aus.

## Aus dem Repository abgeleitete Produktionsarchitektur

- Checkout: `/opt/git/open-city-planner`
- administrativer SSH-Zugang mit `become`; der konkrete Login bleibt lokale Operator-Konfiguration
- Service-Benutzer: `oklab`
- FastAPI: `127.0.0.1:8008`
- Nuxt/Nitro: `127.0.0.1:3008`
- MapLibre-Native-Vorschaurenderer: eigener Benutzer und Dienst `stadtplaner-map-renderer`, nur `127.0.0.1:3020`; der von FastAPI verwaltete persistente Cache liegt unter `/data/stadtplaner/previews`
- PostgreSQL/PostGIS: fachliche Source of Truth
- Redis: Cache und produktive Rate-Limit-Zähler
- Nginx: Reverse Proxy für Frontend/API und optional Entwicklerdokumentation
- Certbot: bestehende Let's-Encrypt-Zertifikate; neue Zertifikate nur über ein separates Playbook
- OSM: `scripts/osm/*`, persistente Daten unter `/data/stadtplaner`, stündlicher systemd-Timer
- Kommunale Statistik: wöchentlicher Import-Timer
- E-Mail-Outbox: minütlicher Timer
- Mastodon Publisher: optionaler minütlicher Timer
- OpenTelemetry Collector: OTLP/gRPC nur auf `127.0.0.1:4317`, Health auf `127.0.0.1:13133`
- Grafana Tempo: lokales Trace-Backend auf `127.0.0.1:3200`, 14 Tage Retention

Backend-Settings werden aus `backend/.env` geladen. Jeder Release erhält dafür einen geschützten Snapshot unter `/etc/stadtplaner/releases/<sha>/backend.env`; `/etc/stadtplaner/backend.env` zeigt auf den aktiven Snapshot. Für das Frontend gilt dasselbe mit `frontend.env`. Verzeichnisse sind `root:oklab`/`0750`, Dateien `root:oklab`/`0640`; Secrets liegen nicht im Git-Checkout und werden mit `no_log` verarbeitet. Der OSM-Sync liest weiterhin `/etc/stadtplaner/osm-sync.env`.

## Controller installieren

Ansible sollte **nicht aus dem produktiven Checkout `/opt/git/open-city-planner` heraus** laufen, weil dieser Checkout während des Deployments aktualisiert wird. Nutze einen separaten Admin-/Workstation-Checkout.

Auf Debian/Ubuntu beispielsweise:

```bash
python3 -m venv ~/.venvs/stadtplaner-ansible
~/.venvs/stadtplaner-ansible/bin/pip install --require-hashes --requirement requirements.txt
cd /pfad/zum/open-city-planner/deploy/ansible
```

Das committed Inventory verwendet den öffentlichen Stadtplaner-Hostnamen, aber absichtlich keinen SSH-Benutzernamen oder private SSH-Optionen. Für den aktuellen Operator kann der Login lokal gesetzt werden, zum Beispiel:

```bash
export ANSIBLE_REMOTE_USER=DEPLOY_USER
ansible stadtplaner -m ping
ansible stadtplaner -b -m command -a 'id'
```

Alternativ kann der Login in `~/.ssh/config` oder einem nicht committeten lokalen Inventory gesetzt werden. SSH Host Keys bleiben absichtlich aktiviert.

Temporäre Moduldateien legt der Controller unter `/tmp` auf dem Zielhost ab. Ansible erzeugt dort für jeden Task ein zufälliges, nur für den SSH-Benutzer zugängliches Unterverzeichnis. Damit hängt ein Deploy nicht von einem möglicherweise veralteten oder falsch berechtigten `~/.ansible/tmp` eines Operators ab.

## DNS-Preflight

Bootstrap, normaler Deploy und Zertifikatsausstellung beginnen mit einem DNS-Preflight. Er löst die benötigten Hostnamen auf dem Controller auf und verlangt mindestens eine Übereinstimmung mit `stadtplaner_expected_dns_addresses`. Standardmäßig werden öffentliche Website und API geprüft; die Entwickler-Subdomain kommt bei ihrer Aktivierung und immer vor ihrem Zertifikats-Playbook hinzu. Falsche oder noch nicht propagierte Einträge stoppen den Lauf vor jeder Installationsänderung.

Der Preflight kann auch separat ausgeführt werden:

```bash
ANSIBLE_REMOTE_USER=DEPLOY_USER ansible-playbook playbooks/preflight.yml \
  -e @~/stadtplaner-vault.yml \
  --ask-vault-pass
```

Für ein anderes Zielsystem müssen im externen Vault dessen öffentliche Adressen stehen:

```yaml
stadtplaner_expected_dns_addresses:
  - 203.0.113.10
  - 2001:db8::10
```

`stadtplaner_require_dns_preflight=false` ist nur für bewusst offline vorbereitete Testsysteme vorgesehen.

## Einmalige Voraussetzungen

`bootstrap.yml` richtet die vorhandene, über `/usr/share/keyrings/nodesource.gpg`
verifizierte NodeSource-Paketquelle ein und installiert die festgelegten Node-,
Corepack- und pnpm-Versionen. Außerdem installiert es uv 0.12.5 isoliert und damit
die verwaltete Python-Version 3.12.14. Die globale
Nginx-/PostgreSQL-/Redis-Konfiguration bleibt unverändert.

```bash
ansible-playbook playbooks/bootstrap.yml
```

Erwartet werden unter anderem ein Bootstrap-Python 3.12+, der vorhandene
NodeSource-Schlüsselbund, Nginx, Certbot, PostgreSQL-Client, Redis-CLI,
`osm2pgsql` und `osmium`. Ansible verwaltet exakt Python 3.12.14, uv 0.12.5,
Node.js 22.23.2, Corepack 0.35.0 und pnpm 11.22.0. Mit
`stadtplaner_manage_node_runtime=false` kann die globale Node-Verwaltung bewusst
abgeschaltet werden; die exakte Versionsprüfung bleibt aktiv.

## Secrets und Environment

Bestehende Produktionsdateien können unverändert unter `/etc/stadtplaner/` verbleiben. Alternativ kann Ansible sie aus einem **extern gespeicherten verschlüsselten Vault** schreiben.

```bash
cp vault.example.yml ~/stadtplaner-vault.yml
ansible-vault encrypt ~/stadtplaner-vault.yml
```

Danach:

```bash
ansible-playbook playbooks/deploy.yml \
  -e @~/stadtplaner-vault.yml \
  --ask-vault-pass \
  -e stadtplaner_deploy_ref=<commit-sha>
```

`vault.example.yml` ist die vollständige Eingabereferenz: Es führt alle Schlüssel aus `backend/.env.example`, `frontend/.env.example` und `deploy/osm-sync.env.example` sowie sämtliche überschreibbaren Deployment- und Runtime-Variablen auf. Pflichtwerte sind deutlich mit `REPLACE_…` markiert; optionale Integrationen bleiben standardmäßig deaktiviert. Reale Secrets niemals committen.

## Automatischer Deploy über GitHub Actions

`.github/workflows/deploy.yml` deployt einen Push auf `main` automatisch, sobald der zugehörige Workflow **Release Gate** erfolgreich beendet wurde. Dieses Gate bündelt Backend-, Frontend-, E2E- und Security-Prüfungen; nur ein erfolgreicher Gate-Lauf für einen `push` auf `main` löst den automatischen Produktionsdeploy aus. Für automatische Läufe verwendet der Workflow `workflow_run.head_sha`, sodass exakt der erfolgreich gegatete Commit ausgerollt wird. Ein manueller Start per `workflow_dispatch` ist weiterhin nur auf `main` möglich, wird aber zusätzlich blockiert, bis für denselben Commit bereits ein erfolgreicher Release-Gate-Lauf existiert. Eine Concurrency-Gruppe lässt nie zwei Produktionsdeployments gleichzeitig laufen.

Lege im Repository unter **Settings → Environments** die Environment `production` an und beschränke sie auf den Branch `main`. Ein Required Reviewer ist optional: Ohne Reviewer läuft der Deploy vollautomatisch; mit Reviewer wartet er vor dem Zugriff auf die Secrets auf eine Freigabe.

GitHub Actions verwendet absichtlich keinen Base64-kodierten Ansible Vault. GitHub verschlüsselt Environment Secrets bereits; Vault-Datei und Vault-Passwort gemeinsam dort abzulegen würde die Secret-Verwaltung nur doppeln. Stattdessen werden skalare Zugangsdaten einzeln gespeichert und erst auf dem temporären Runner mit der nicht-sensitiven Konfiguration zusammengesetzt.

Lege unter **Environment variables** drei mehrzeilige Konfigurationswerte an:

- `STADTPLANER_BACKEND_ENV_CONFIG`: vollständige Backend-Konfiguration ohne die unten aufgeführten Secret-Schlüssel;
- `STADTPLANER_FRONTEND_ENV_CONFIG`: vollständiger Inhalt von `frontend/.env`;
- `STADTPLANER_OSM_ENV_CONFIG`: vollständiger Inhalt von `deploy/osm-sync.env`.

Die drei Blöcke müssen alle zugehörigen Schlüssel aus `vault.example.yml` enthalten. Aus dem Backend-Block müssen `DATABASE_URL`, `JWT_SECRET_KEY`, `OAUTH_STATE_SECRET`, `MFA_RECOVERY_PEPPER`, `MFA_ENCRYPTION_KEY`, `SMTP_HOST`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `CONTACT_TO_EMAIL`, `CONTACT_TO_NAME`, `REDIS_URL`, `TURNSTILE_SECRET_KEY`, `GITHUB_CLIENT_SECRET`, `GOOGLE_CLIENT_SECRET`, `MASTODON_SSO_ENCRYPTION_KEY`, `NOMINATIM_BASE_URL` und `NOMINATIM_EMAIL` entfernt werden. Der Workflow lehnt doppelte, fehlende, zusätzliche oder versehentlich offen eingetragene Secret-Schlüssel ab.

`OCP_ENABLED_INSTALLED_BACKEND_PATHS` und `OCP_INSTALLED_FRONTEND_MODULE_ROOTS` bleiben in
den Eingabeblöcken leer. Die Rolle rendert beide Werte sowie das Enablement separat
aus dem strict validierten [`modules.lock`](../../docs/modules/installer.md) im
host-owned `stadtplaner_module_install_root` und bindet sie vor den Modul-
Preflights an den target Environment-Snapshot.

Optionale Registry-Installationen werden mit `stadtplaner_registry_modules` als
Liste aus `id`, exakter `version` und `expected_sha256` deklariert. Die Registry-
Basis setzt `stadtplaner_module_registry_url` (Default: produktive OCP Registry).
Die leere Liste deaktiviert jeden Netzwerkzugriff. Die Rolle installiert gepinnte
Bundles nach dem Backend-Sync und vor dem Rendern von `modules.lock`; sie aktiviert
Module niemals automatisch. Beispielwerte stehen in `vault.example.yml`.

Aktive Module verwenden ausschließlich
`OCP_MODULE_<MODULE-ID>_<SETTING>`. Hinterlege diese dynamische, potentiell geheime
Zusatzkonfiguration gesammelt im optionalen Environment Secret
`STADTPLANER_MODULE_ENV_CONFIG`, nicht in einer GitHub Environment Variable. Der
Builder akzeptiert in diesem Block nur das Modulpräfix, lehnt doppelte Keys ab und
hängt ihn ohne Wertausgabe an dieselbe atomare Backend-Environmentdatei an. Details
zu Schema, Defaults, Secrets und Public Export stehen in
[`docs/modules/configuration.md`](../../docs/modules/configuration.md).

`STADTPLANER_BACKEND_ENV_CONFIG` muss für Produktion außerdem exakt die
OpenTelemetry-Werte aus `vault.example.yml` enthalten: Tracing aktiviert,
Service `stadtplaner-api`, gRPC und `http://127.0.0.1:4317`. Der Builder prüft
Scheme, Host, expliziten Port sowie das Fehlen von Credentials, Pfad, Query und
Fragment, bevor SSH verwendet wird. Der Endpoint selbst ist kein Secret; der
gesamte Environment-Block bleibt dennoch gemäß der Deployment-Policy geschützt.

Unter **Environment secrets** gehören die vier Deployment-Zugangsdaten:

- `STADTPLANER_ANSIBLE_REMOTE_USER`
- `STADTPLANER_SSH_PRIVATE_KEY`
- `STADTPLANER_SSH_KNOWN_HOSTS`
- `STADTPLANER_BECOME_PASSWORD`
- optional bei aktivierten Modulen: `STADTPLANER_MODULE_ENV_CONFIG`

Hinzu kommen die individuellen Applikations-Secrets:

- `STADTPLANER_DATABASE_URL`
- `STADTPLANER_JWT_SECRET_KEY`
- `STADTPLANER_OAUTH_STATE_SECRET`
- `STADTPLANER_MFA_RECOVERY_PEPPER`
- `STADTPLANER_MFA_ENCRYPTION_KEY`
- `STADTPLANER_SMTP_HOST`, `STADTPLANER_SMTP_USERNAME`, `STADTPLANER_SMTP_PASSWORD`, `STADTPLANER_SMTP_FROM_EMAIL`
- `STADTPLANER_CONTACT_TO_EMAIL`, `STADTPLANER_CONTACT_TO_NAME`
- `STADTPLANER_REDIS_URL`
- optional je nach aktivierter Integration: `STADTPLANER_TURNSTILE_SECRET_KEY`, `STADTPLANER_GITHUB_CLIENT_SECRET`, `STADTPLANER_GOOGLE_CLIENT_SECRET`, `STADTPLANER_MASTODON_SSO_ENCRYPTION_KEY`, `STADTPLANER_NOMINATIM_BASE_URL`, `STADTPLANER_NOMINATIM_EMAIL`.

Secret-Werte können mit `gh secret set NAME --env production` interaktiv gesetzt werden, ohne sie als Kommandozeilenargument in die Shell-History zu schreiben. Für Dateiwerte gilt beispielsweise:

```bash
gh secret set STADTPLANER_SSH_PRIVATE_KEY --env production < ~/.ssh/STADTPLANER_CI_KEY
ssh-keygen -F stadtplaner.oklabflensburg.de -f ~/.ssh/known_hosts \
  | sed '/^#/d' \
  | gh secret set STADTPLANER_SSH_KNOWN_HOSTS --env production
```

Den Host-Key vor dem Hochladen gegen einen bereits vertrauenswürdig bekannten Fingerprint prüfen. Niemals die Host-Key-Prüfung abschalten. Der Runner schreibt die zusammengesetzten Ansible-Variablen und Zugangsdaten nur mit Modus `0600` in sein temporäres Verzeichnis und entfernt sie auch nach einem Fehler. Das lokale Ansible Vault bleibt für manuelle Deployments verwendbar, ist aber keine Eingabe des GitHub-Workflows mehr.

## Datenbankbackup vor Migrationen

Vor dem modulbewussten Migrations-Preflight und Upgrade erstellt Ansible
standardmäßig einen Custom-Format-Dump unter `/var/backups/stadtplaner`.
`pg_dump` läuft als lokaler PostgreSQL-Systembenutzer `postgres` über
Peer-Authentifizierung und liest die Datenbank nur; Datenbankzugangsdaten werden
weder ausgelesen noch auf der Kommandozeile offengelegt. Ein 30-sekündiges
Lock-Limit verhindert unbegrenztes Warten auf konkurrierende DDL. Der Lauf
schreibt zunächst eine restriktiv berechtigte `.partial`-Datei, verlangt einen
nicht leeren Dump, validiert ihn mit `pg_restore --list` und benennt ihn erst
danach atomar zum endgültigen Archiv um. Nur ein erfolgreich veröffentlichtes
Archiv gibt `python -m app.cli.module_migrations preflight` und das anschließende
`upgrade` frei. Beide Schritte erhalten den konfigurierten
`OCP_MODULE_INSTALL_ROOT` explizit.

Standardmäßig werden die drei neuesten validierten Dumps aufbewahrt (`stadtplaner_database_backup_retention`). Vor einem neuen Dump werden ältere Archive so bereinigt, dass bei einem fehlgeschlagenen Backup noch zwei validierte Sicherungen verbleiben. Verwaiste `.partial`-Dateien entfernt Ansible nach zehn Minuten.

Die Standardkonfiguration lautet:

```yaml
stadtplaner_database_backup_mode: managed
stadtplaner_database_name: open_city_map
stadtplaner_database_backup_dir: /var/backups/stadtplaner
stadtplaner_database_backup_retention: 3
```

Für eine externe Backup-Lösung kann stattdessen bewusst `custom` gewählt werden. Der Befehl muss mit einem Fehlercode ungleich null abbrechen, wenn kein verifiziertes Backup erzeugt wurde:

```yaml
stadtplaner_database_backup_mode: custom
stadtplaner_pre_migration_backup_command: /usr/local/sbin/stadtplaner-backup-before-deploy
```

Für einen Deploy ohne Schemaänderungen kann bewusst gesetzt werden:

```bash
-e stadtplaner_run_migrations=false
```

Nicht dauerhaft den Backup-Guard abschalten.

## Normaler Deploy nach einem Push

Am sichersten wird **ein konkreter Commit** deployed, nicht ein beweglicher Branchname:

```bash
git fetch origin
SHA=$(git rev-parse origin/main)
cd deploy/ansible
ANSIBLE_REMOTE_USER=DEPLOY_USER ansible-playbook playbooks/deploy.yml \
  -e @~/stadtplaner-vault.yml \
  --ask-vault-pass \
  -e stadtplaner_deploy_ref="$SHA"
```

Der konkrete Deploy-Ref steht absichtlich hinter der Vault-Datei. So kann ein
veralteter `stadtplaner_deploy_ref` im Vault den ausgewählten Commit nicht
überschreiben.

Der Ablauf ist:

1. die gepinnten Python-, uv-, Node-, Corepack- und pnpm-Toolchains installieren beziehungsweise prüfen;
2. gepinnte Collector-/Tempo-Binaries samt Checksummen installieren, beide Dienste starten und OTLP-, Health- und Tempo-Readiness vorprüfen;
3. persistente Env-Dateien prüfen/schreiben und die produktive OpenTelemetry-Policy erzwingen;
4. Git auf exakt den gewünschten Ref aktualisieren, ohne lokale Änderungen zu verwerfen;
5. Backend-Venv per `uv sync --frozen` exakt aus `backend/uv.lock` materialisieren;
6. Frontend-Abhängigkeiten per Lockfile installieren, Nuxt bauen und optional Tests/Typecheck ausführen;
7. das versionierte Release vollständig assemblieren;
8. Backup-Guard, modulbewusster Migrations-Preflight und Upgrade;
9. systemd-Units installieren/aktualisieren;
10. Hintergrund-Timer synchronisieren;
11. Stadtplaner-Nginx-Konfiguration installieren und mit `nginx -t` validieren;
12. gegebenenfalls die alten `stadtplanner-*`-Units kontrolliert stoppen und deaktivieren, Ports freigeben sowie API und Frontend unter den verwalteten `stadtplaner-*`-Units starten;
13. lokale Health-/HTTP-Smoke-Tests und einen echten Trace-Nachweis in Tempo durchführen.

Ein Fehler stoppt den Lauf. `serial: 1` und `any_errors_fatal: true` verhindern ein Weiterrollen nach einem Fehler.

Vor dem Handover prüft Ansible, dass der konfigurierte Service-Benutzer die target Environment-Snapshots lesen und der target Backend-Release seine strikten Settings laden kann. Anschließend stoppt es die verwalteten primären Dienste, verlangt freie Anwendungsports und schaltet Code sowie beide Environment-Symlinks, bevor es die aktuellen Units startet. Frühere `stadtplanner-*`-Legacy-Units werden nicht mehr durch das Deployment verwaltet und müssen vor dem ersten Handover administrativ entfernt werden.

## Release-Verzeichnisse und Rollback

Jeder Produktionsdeploy baut ein eigenes, unveränderliches Release-Verzeichnis unter `/opt/stadtplaner/releases/<sha>` und passende Environment-Snapshots unter `/etc/stadtplaner/releases/<sha>` auf. Vor der Aktivierung validiert der target Backend-Release seine strikten Settings gegen den target Snapshot. Während API, Frontend und Renderer gestoppt sind, werden `/opt/stadtplaner/current`, `/etc/stadtplaner/backend.env` und `/etc/stadtplaner/frontend.env` gemeinsam auf den target Stand geschaltet. Eine zuvor aktive Code-/Konfigurationseinheit bleibt als direktes Rollback-Ziel erhalten, bis die konfigurierte Retention (`stadtplaner_release_retention`) erreicht ist.

Nach dem Aktivieren der Services führt Ansible als Smoke-Tests lokale Health-
und Frontend-Checks, binärsichere WebP-Downloads sowie einen gepollten
Trace-Nachweis in Tempo aus. WebP-Daten werden in eine temporäre Datei geladen,
als RIFF/WEBP-Bytes validiert und zuverlässig gelöscht; sie durchlaufen nie
Ansibles UTF-8-Deserialisierung. Wenn ein Test fehlschlägt, werden Code- und
Environment-Symlinks auf den vorherigen Release zurückgesetzt und erst danach
die Services neu gestartet. Die ursprüngliche Ursache bleibt neben einem
möglichen Rollbackfehler sichtbar. Der Collector ist
über `Wants`/`After`, aber bewusst nicht über `Requires` an die API gekoppelt:
Ein späterer Telemetrieausfall stoppt keine Nutzeranfragen.

## Optionale Prüfungen auf dem Server

CI sollte die Hauptqualitätsgrenze bleiben. Für ein besonders sensibles Release können zusätzlich aktiviert werden:

```bash
-e stadtplaner_run_backend_tests=true \
-e stadtplaner_run_frontend_tests=true \
-e stadtplaner_run_frontend_typecheck=true
```

Diese Prüfungen verlängern das Produktionsdeployment und sind standardmäßig aus. Für Backend-Pytest müssen die Development-Extras im produktiven Venv vorhanden sein; im Normalbetrieb wird deshalb die CI als Testgrenze empfohlen.

## Nginx und Rate Limits

Ansible ersetzt **nicht** `/etc/nginx/nginx.conf`. Es verwaltet nur:

- `/etc/nginx/conf.d/stadtplaner-rate-limits.conf`
- `/etc/nginx/sites-available/stadtplaner`
- `/etc/nginx/sites-enabled/stadtplaner`

Damit bleiben die vielen anderen Projekte auf dem Shared Host außerhalb dieses Deployments. Die Rate-Limit-Zonen stammen aus `deploy/nginx/conf.d/stadtplaner-rate-limits.conf`.

Initial ist `stadtplaner_enable_rate_limit_dry_run: true`. Erst nach Auswertung von `REJECTED_DRY_RUN` sollte auf echte 429-Ablehnung umgestellt werden:

```bash
-e stadtplaner_enable_rate_limit_dry_run=false
```

FastAPI/Redis bleibt die fachlich zuständige Rate-Limit-Schicht.

## Entwickler-Subdomain und Certbot

Die Entwickler-Subdomain ist standardmäßig aus, damit ein fehlendes Zertifikat niemals `nginx -t` kaputt macht.

Nach gesetztem DNS zunächst einmalig:

```bash
ANSIBLE_REMOTE_USER=DEPLOY_USER ansible-playbook playbooks/certificates.yml \
  -e stadtplaner_manage_certificates=true \
  -e stadtplaner_certbot_email=DEINE-ADMIN-MAIL
```

Danach deployen mit:

```bash
-e stadtplaner_enable_developer_host=true
```

Normale Deployments führen Certbot nicht aus. Die reguläre Certbot-Renewal-Infrastruktur des Servers bleibt zuständig.

## OSM

Der Initialimport ist absichtlich aus dem normalen Deployment ausgeschlossen. Er ist groß, extern datenabhängig und darf nur explizit gestartet werden:

```bash
ANSIBLE_REMOTE_USER=DEPLOY_USER ansible-playbook playbooks/osm-initial-import.yml \
  -e confirm_osm_initial_import=true
```

Vorher `docs/osm-hourly-sync.md` und `/etc/stadtplaner/osm-sync.env` prüfen. Der normale Deploy installiert nur den stündlichen Sync-Timer.

## Hintergrunddienste

Standardmäßig:

- `stadtplaner-osm-update.timer`: aktiv
- `stadtplaner-email-outbox.timer`: aktiv
- `stadtplaner-domain-event-outbox.timer`: aktiv

## Rollback

Für Code ohne inkompatible Datenbankänderung kann ein zuvor bekannter Commit wieder deployed werden:

```bash
ANSIBLE_REMOTE_USER=DEPLOY_USER ansible-playbook playbooks/deploy.yml \
  -e stadtplaner_deploy_ref=<previous-good-sha> \
  -e stadtplaner_run_migrations=false
```

Bei Datenbankmigrationen entscheidet die konkrete Migration plus Backup über den Rollback. Das Playbook führt niemals automatisch `alembic downgrade` aus.

## Nachkontrolle

```bash
sudo systemctl status stadtplaner-api stadtplaner-frontend
sudo systemctl list-timers 'stadtplaner-*'
sudo nginx -t
curl --fail https://api.stadtplaner.oklabflensburg.de/health
```

Für Nginx-Dry-Run-Limits:

```bash
grep REJECTED_DRY_RUN /var/log/nginx/access.log
```

## Was Ansible bewusst nicht verwaltet

- globale `/etc/nginx/nginx.conf` für alle Projekte;
- PostgreSQL-Cluster-/Rollen-/Firewall-Konfiguration des Shared Hosts;
- Redis-Serverkonfiguration anderer Anwendungen;
- Firewall/SSH des gesamten Servers;
- DNS;
- automatische Certbot-Ausstellung bei jedem Deploy;
- OSM-Initialimport bei jedem Deploy;
- echte Secrets im Repository;
- automatische Datenbank-Downgrades.

Diese Grenzen sind Absicht: Das Stadtplaner-Repository soll andere Dienste auf demselben Server nicht unbeabsichtigt verändern.
