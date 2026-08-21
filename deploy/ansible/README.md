# Ansible Deployment

Dieses Verzeichnis automatisiert den produktiven Betrieb des Open City Planner auf dem bestehenden Shared Host. Es ersetzt bewusst nicht die globale Serververwaltung aller OK-Lab-Projekte. Nginx, PostgreSQL, Redis und Node können weitere Anwendungen bedienen; die Playbooks verändern deshalb nur Stadtplaner-spezifische Dateien und prüfen globale Voraussetzungen, statt `/etc/nginx/nginx.conf`, PostgreSQL oder Redis blind neu zu konfigurieren.

## Warum Ansible?

Für diesen Server ist ein idempotenter Deployment-Ablauf sicherer als wiederholte manuelle Änderungen: dieselben Pfade, Benutzer, systemd-Units, Builds, Migrationen, Nginx-Dateien und Smoke Tests werden bei jedem Lauf reproduzierbar angewendet. Ein normaler Deploy führt **keinen** OSM-Initialimport und **keine** Certbot-Ausstellung aus.

## Aus dem Repository abgeleitete Produktionsarchitektur

- Checkout: `/opt/git/open-city-planner`
- Arbeits-/SSH-Benutzer: `awendelk` mit `become`
- Service-Benutzer: `oklab`
- FastAPI: `127.0.0.1:8008`
- Nuxt/Nitro: `127.0.0.1:3008`
- PostgreSQL/PostGIS: fachliche Source of Truth
- Redis: Cache und produktive Rate-Limit-Zähler
- Nginx: Reverse Proxy für Frontend/API und optional Entwicklerdokumentation
- Certbot: bestehende Let's-Encrypt-Zertifikate; neue Zertifikate nur über ein separates Playbook
- OSM: `scripts/osm/*`, persistente Daten unter `/data/stadtplaner`, stündlicher systemd-Timer
- Kommunale Statistik: wöchentlicher Import-Timer
- E-Mail-Outbox: minütlicher Timer
- Mastodon Publisher: optionaler minütlicher Timer

Backend-Settings werden aus `backend/.env` geladen. Ansible verlinkt diese Datei auf `/etc/stadtplaner/backend.env`, damit Secrets nicht im Git-Checkout liegen. Für das Frontend wird analog `/etc/stadtplaner/frontend.env` verwendet. Der OSM-Sync liest `/etc/stadtplaner/osm-sync.env`.

## Controller installieren

Ansible sollte **nicht aus dem produktiven Checkout `/opt/git/open-city-planner` heraus** laufen, weil dieser Checkout während des Deployments aktualisiert wird. Nutze einen separaten Admin-/Workstation-Checkout.

Auf Debian/Ubuntu beispielsweise:

```bash
python3 -m venv ~/.venvs/stadtplaner-ansible
~/.venvs/stadtplaner-ansible/bin/pip install 'ansible-core>=2.17,<2.20'
cd /pfad/zum/open-city-planner/deploy/ansible
```

Der Inventory-Eintrag verwendet `89.58.56.254` und `awendelk`. SSH Host Keys bleiben absichtlich aktiviert. Test:

```bash
ansible stadtplaner -m ping
ansible stadtplaner -b -m command -a 'id'
```

## Einmalige Voraussetzungen

`bootstrap.yml` prüft bewusst nur den vorhandenen Shared Host und legt Stadtplaner-Verzeichnisse an. Es fügt keine fremden APT-Repositories hinzu und ersetzt keine globale Nginx-/PostgreSQL-/Redis-Konfiguration.

```bash
ansible-playbook playbooks/bootstrap.yml
```

Erwartet werden unter anderem Python 3.12+, Node 22, Corepack, Nginx, Certbot, PostgreSQL-Client, Redis-CLI, `osm2pgsql` und `osmium`.

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

`vault.example.yml` enthält nur Platzhalter. Reale Secrets niemals committen.

## Datenbankbackup vor Migrationen

Das Playbook verlangt standardmäßig einen expliziten Backup-Befehl, bevor `alembic upgrade head` ausgeführt wird. Das Repository kennt absichtlich keine Produktions-Datenbank-Credentials und erfindet daher keinen `pg_dump`-Aufruf.

Beispiel als verschlüsselte Variable:

```yaml
stadtplaner_pre_migration_backup_command: >-
  /usr/local/sbin/stadtplaner-backup-before-deploy
```

Der angegebene Befehl muss selbst mit Fehlercode != 0 abbrechen, wenn kein verifiziertes Backup erzeugt werden konnte. Für einen Deploy ohne Schemaänderungen kann bewusst gesetzt werden:

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
ansible-playbook playbooks/deploy.yml \
  -e stadtplaner_deploy_ref="$SHA" \
  -e @~/stadtplaner-vault.yml \
  --ask-vault-pass
```

Der Ablauf ist:

1. Runtime-Versionen prüfen.
2. persistente Env-Dateien prüfen/schreiben;
3. Git auf exakt den gewünschten Ref aktualisieren, ohne lokale Änderungen zu verwerfen;
4. Backend-Venv und Python-Abhängigkeiten aktualisieren;
5. Frontend-Abhängigkeiten per Lockfile installieren und Nuxt bauen;
6. optional Tests/Typecheck ausführen;
7. Backup-Guard und Alembic-Migrationen;
8. systemd-Units installieren/aktualisieren;
9. Hintergrund-Timer synchronisieren;
10. Stadtplaner-Nginx-Konfiguration installieren und mit `nginx -t` validieren;
11. API und Frontend kontrolliert neu starten;
12. lokale Health-/HTTP-Smoke-Tests durchführen.

Ein Fehler stoppt den Lauf. `serial: 1` und `any_errors_fatal: true` verhindern ein Weiterrollen nach einem Fehler.

## Optionale Prüfungen auf dem Server

CI sollte die Hauptqualitätsgrenze bleiben. Für ein besonders sensibles Release können zusätzlich aktiviert werden:

```bash
-e stadtplaner_run_backend_tests=true \
-e stadtplaner_run_frontend_tests=true \
-e stadtplaner_run_frontend_typecheck=true
```

Diese Prüfungen verlängern das Produktionsdeployment und sind standardmäßig aus.

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
ansible-playbook playbooks/certificates.yml \
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
ansible-playbook playbooks/osm-initial-import.yml \
  -e confirm_osm_initial_import=true
```

Vorher `docs/osm-hourly-sync.md` und `/etc/stadtplaner/osm-sync.env` prüfen. Der normale Deploy installiert nur den stündlichen Sync-Timer.

## Hintergrunddienste

Standardmäßig:

- `stadtplaner-osm-update.timer`: aktiv
- `stadtplaner-flensburg-statistics-sync.timer`: aktiv
- `stadtplaner-email-outbox.timer`: aktiv
- `stadtplaner-social-publisher.timer`: aus

Mastodon nur aktivieren, wenn die Backend-Konfiguration vollständig ist:

```bash
-e stadtplaner_enable_social_publisher_timer=true
```

## Rollback

Für Code ohne inkompatible Datenbankänderung kann ein zuvor bekannter Commit wieder deployed werden:

```bash
ansible-playbook playbooks/deploy.yml \
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
