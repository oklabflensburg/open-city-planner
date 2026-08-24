# Prometheus und Grafana mit Ansible betreiben

Das separate Playbook `deploy/ansible/playbooks/monitoring.yml` installiert und
konfiguriert einen self-hostbaren Monitoring-Stack für den Stadtplaner:

- Prometheus sammelt API-, Host- und Job-Metriken und wertet die versionierten Alert-Regeln aus;
- Grafana erhält Prometheus als vorinstallierte Datenquelle und lädt das Stadtplaner-Dashboard automatisch;
- Grafana erhält das vom normalen Deploy verwaltete Tempo als vorinstallierte Trace-Datenquelle;
- der Blackbox Exporter prüft `/health/ready` aus Sicht des Monitoring-Hosts;
- der Node Exporter liefert Host-Metriken und liest die `.prom`-Dateien der timerbasierten Jobs.

Das normale `deploy.yml` installiert den Monitoring-Stack bewusst nicht. So
bleiben bestehende Shared Hosts unverändert, bis der Operator `monitoring.yml`
ausdrücklich ausführt.

## Brauche ich Subdomains?

Nein. Die sichere Standardkonfiguration bindet alle Dienste ausschließlich an
Loopback:

| Dienst | Standardadresse | Öffentlich |
| --- | --- | --- |
| Grafana | `127.0.0.1:3000` | nein |
| Prometheus | `127.0.0.1:9090` | nein |
| Node Exporter | `127.0.0.1:9100` | nein |
| Blackbox Exporter | `127.0.0.1:9115` | nein |
| Tempo | `127.0.0.1:3200` | nein |

Grafana kann dann über einen SSH-Tunnel benutzt werden. Eine DNS-Subdomain ist
nur für den optionalen öffentlichen HTTPS-Zugang zu Grafana erforderlich.
Prometheus und die Exporter sollten nicht öffentlich veröffentlicht werden.

## Voraussetzungen

- Debian oder Ubuntu auf dem Zielhost;
- SSH-Zugang mit `become`;
- ausreichend Speicherplatz für die konfigurierte Prometheus-Retention;
- ein bereits deployter Stadtplaner, dessen Backend standardmäßig auf `127.0.0.1:8008` hört;
- ein gemäß der [Ansible-Anleitung](../deploy/ansible/README.md) eingerichteter Controller;
- ausgehender HTTPS-Zugriff auf `apt.grafana.com`, sofern das offizielle Grafana-Repository noch fehlt.

Prometheus und die Exporter kommen aus den signierten Betriebssystemquellen.
Grafana OSS kommt aus dem offiziellen, per `signed-by` isolierten
Grafana-APT-Repository. `monitoring_grafana_package_version` kann eine konkrete
Paketversion festlegen. Ohne Angabe installiert Ansible das angebotene Paket
nur, wenn Grafana noch fehlt; normale Läufe erzwingen kein Upgrade.
Der heruntergeladene Repository-Schlüssel wird zusätzlich gegen den im
Repository dokumentierten Fingerprint geprüft. Eine Schlüsselrotation muss
bewusst anhand der offiziellen Grafana-Mitteilung nachvollzogen werden.

## 1. Inventory prüfen

Das Produktions-Inventory enthält denselben Host in den Gruppen `stadtplaner`
und `monitoring`. Für einen separaten Monitoring-Server wird ein eigenes Ziel
eingetragen:

```yaml
all:
  children:
    stadtplaner:
      hosts:
        stadtplaner-prod:
          ansible_host: stadtplaner.example.org
    monitoring:
      hosts:
        stadtplaner-monitoring:
          ansible_host: monitoring-internal.example.org
```

Ein Verbindungstest verändert nichts:

```bash
cd deploy/ansible
ANSIBLE_REMOTE_USER=DEPLOY_USER ansible monitoring -m ping
```

## 2. Externen Vault ergänzen

Erzeuge ein langes, zufälliges Passwort lokal und trage es direkt in den
bereits verschlüsselten externen Vault ein:

```bash
openssl rand -base64 36
ansible-vault edit ~/stadtplaner-vault.yml
```

Mindestens erforderlich:

```yaml
monitoring_grafana_admin_user: admin
monitoring_grafana_admin_password: EIN_LANGES_ZUFAELLIGES_PASSWORT
monitoring_grafana_publish: false
```

Reale Passwörter dürfen niemals nach `vault.example.yml` geschrieben oder
committet werden. Das Bootstrap-Passwort wird von Grafana nur beim erstmaligen
Erstellen seiner Datenbank verwendet. Eine spätere Änderung der Vault-Variable
ändert ein vorhandenes Grafana-Konto nicht automatisch.

## 3. Konfiguration vorab prüfen

```bash
cd deploy/ansible
ANSIBLE_REMOTE_USER=DEPLOY_USER ansible-playbook \
  --syntax-check playbooks/monitoring.yml

ANSIBLE_REMOTE_USER=DEPLOY_USER ansible-playbook playbooks/monitoring.yml \
  -e @~/stadtplaner-vault.yml \
  --ask-vault-pass \
  --check --diff
```

APT-Installationen und Service-Healthchecks lassen sich im Check Mode nicht in
jeder Umgebung vollständig simulieren. Der Syntaxcheck bleibt deshalb die
verlässliche statische Vorprüfung.

## 4. Stack installieren

```bash
cd deploy/ansible
ANSIBLE_REMOTE_USER=DEPLOY_USER ansible-playbook playbooks/monitoring.yml \
  -e @~/stadtplaner-vault.yml \
  --ask-vault-pass
```

Das Playbook:

1. validiert Betriebssystem, Passwort und Bind-Konfiguration;
2. installiert Prometheus, Node Exporter, Blackbox Exporter und Grafana OSS;
3. konfiguriert Retention und ausschließlich lokale Listener;
4. installiert Alert-Regeln und die Readiness-Probe;
5. aktiviert den Textfile Collector für Stadtplaner-Jobs;
6. provisioniert Prometheus- und Tempo-Datenquellen sowie das Grafana-Dashboard;
7. validiert Prometheus mit `promtool`;
8. startet und aktiviert alle Dienste;
9. prüft Prometheus- und Grafana-Healthendpoints sowie den API-Scrape und die Readiness-Probe.

## 5. Zugriff ohne Subdomain

Baue von der eigenen Workstation einen SSH-Tunnel auf:

```bash
ssh -N \
  -L 3000:127.0.0.1:3000 \
  -L 9090:127.0.0.1:9090 \
  DEPLOY_USER@stadtplaner.example.org
```

Danach sind Grafana unter `http://127.0.0.1:3000` und Prometheus unter
`http://127.0.0.1:9090` erreichbar. Das provisionierte Dashboard liegt in
Grafana im Ordner **Stadtplaner**; Prometheus ist bereits als Standarddatenquelle
verbunden.

## 6. Installation verifizieren

```bash
systemctl --no-pager --full status \
  prometheus prometheus-node-exporter \
  prometheus-blackbox-exporter grafana-server

curl --fail http://127.0.0.1:9090/-/ready
curl --fail http://127.0.0.1:3000/api/health
curl --fail http://127.0.0.1:9100/metrics >/dev/null
curl --fail 'http://127.0.0.1:9115/probe?module=http_2xx&target=http://127.0.0.1:8008/health/ready'
promtool check config /etc/prometheus/prometheus.yml
promtool check rules /etc/prometheus/rules/stadtplaner-alerts.yml
```

In Prometheus unter **Status → Targets** müssen `prometheus`,
`stadtplaner-api`, `stadtplaner-node`, `stadtplaner-readiness` und
`stadtplaner-otel-collector` den Zustand
`UP` zeigen. Die ACL des Job-Metrikverzeichnisses gibt nur dem
Prometheus-Systemkonto zusätzlichen Lesezugriff; Applikations-Secrets werden
nicht freigegeben.

## 7. Retention und Backups

Standardmäßig bewahrt Prometheus höchstens 30 Tage beziehungsweise 10 GB auf:

```yaml
monitoring_prometheus_retention_time: 30d
monitoring_prometheus_retention_size: 10GB
```

Die zuerst erreichte Grenze greift. Vor einer Erhöhung freien Speicher prüfen:

```bash
df -h /var/lib/prometheus
du -sh /var/lib/prometheus/metrics2
```

Die Grafana-Datenbank `/var/lib/grafana/grafana.db` gehört in das Serverbackup.
Provisionierte Dashboards und Datenquellen liegen im Git-Repository und lassen
sich durch Ansible wiederherstellen. Falls die Prometheus-Historie kritisch ist,
muss auch `/var/lib/prometheus` gesichert werden.

## 8. Optionale Grafana-Subdomain

Nur Grafana kann optional über Nginx und HTTPS veröffentlicht werden. Lege
zuerst einen DNS-A/AAAA-Eintrag wie `grafana.stadtplaner.example.org` auf den
Monitoring-Host an und ergänze den verschlüsselten Vault:

```yaml
monitoring_grafana_publish: true
monitoring_grafana_host: grafana.stadtplaner.example.org
monitoring_grafana_certificate_name: grafana.stadtplaner.example.org
monitoring_manage_certificates: true
monitoring_certbot_email: admin@example.org
```

Zertifikat einmalig ausstellen und anschließend den Stack anwenden:

```bash
ANSIBLE_REMOTE_USER=DEPLOY_USER ansible-playbook \
  playbooks/monitoring-certificates.yml \
  -e @~/stadtplaner-vault.yml --ask-vault-pass

ANSIBLE_REMOTE_USER=DEPLOY_USER ansible-playbook \
  playbooks/monitoring.yml \
  -e @~/stadtplaner-vault.yml --ask-vault-pass
```

Nginx erzwingt HTTPS und proxyt nur Grafana. Grafana selbst bleibt auf
`127.0.0.1:3000`; Prometheus und Exporter bleiben intern. Schütze das Login
zusätzlich mit einem starken Passwort und nach Möglichkeit VPN, SSO oder einem
vorgeschalteten Access-Proxy.

## 9. Separater Monitoring-Server

Auf einem separaten Host zeigen Ziel und Readiness-URL auf die API:

```yaml
monitoring_prometheus_api_scheme: https
monitoring_prometheus_api_target: api.stadtplaner.example.org:443
monitoring_readiness_url: https://api.stadtplaner.example.org/health/ready
```

Die am API-Server sichtbare Monitoring-Adresse muss anschließend über einen
normalen Stadtplaner-Deploy freigeschaltet werden:

```yaml
stadtplaner_metrics_allowed_cidrs:
  - 10.20.0.15/32
```

Bei NAT zählt die am API-Server sichtbare Quelladresse. `/metrics` niemals
global freigeben. Ein Node Exporter auf einem separaten Monitoring-Host sieht
nur diesen Host; für Jobmetriken ist zusätzlich ein Exporter auf dem
Applikationsserver oder ein anderer sicherer Transport erforderlich. Für kleine
Installationen ist deshalb derselbe Host die einfachste Variante.

## 10. Alert-Benachrichtigungen

Prometheus wertet die Regeln ohne weitere Komponenten aus und zeigt aktive
Alerts in seiner Oberfläche. Für E-Mail-, Matrix- oder andere
Benachrichtigungen wird zusätzlich ein Alertmanager benötigt. Ein vorhandener
Alertmanager kann verbunden werden:

```yaml
monitoring_alertmanager_targets:
  - 127.0.0.1:9093
```

Das Playbook installiert bewusst keinen Alertmanager und hinterlegt keine
Empfänger-Secrets. Diese gehören in eine separate verschlüsselte Konfiguration.

## 11. Kontrollierte Upgrades

Ein normaler Playbook-Lauf erzwingt kein Upgrade vorhandener Pakete. Verfügbare
Grafana-Versionen lassen sich auf dem Zielhost prüfen und anschließend pinnen:

```bash
apt-cache madison grafana
```

```yaml
monitoring_grafana_package_version: VERSION_AUS_DER_PAKETQUELLE
```

Vor einem größeren Grafana-Upgrade die SQLite-Datenbank sichern. Paketupdates
zuerst auf einem Testsystem prüfen.

## 12. Fehlerdiagnose

### Prometheus-Target ist DOWN

```bash
journalctl -u prometheus -n 200 --no-pager
curl --fail http://127.0.0.1:8008/metrics | head
curl --fail http://127.0.0.1:9090/api/v1/targets
```

Bei einem separaten Host zusätzlich Nginx-Allowlist, Routing, TLS und Quell-IP
prüfen.

### Grafana startet nicht

```bash
journalctl -u grafana-server -n 200 --no-pager
ss -ltnp | grep ':3000'
```

Häufige Ursachen sind ein belegter Port, falsche Dateirechte oder manuelle
Änderungen unter `/etc/grafana`.

### Dashboard zeigt keine Daten

1. Prometheus-Health und Targets prüfen.
2. In Grafana `Stadtplaner Prometheus` unter **Connections → Data sources** testen.
3. Den Dashboard-Zeitraum auf die letzten 15 Minuten stellen.
4. Mit `curl http://127.0.0.1:8008/health/live` Testtraffic erzeugen.

### Jobmetriken fehlen

```bash
namei -l /data/stadtplaner/observability
getfacl /data/stadtplaner/observability
sudo -u prometheus find /data/stadtplaner/observability -maxdepth 1 -name '*.prom' -readable
curl --silent http://127.0.0.1:9100/metrics | grep '^job_'
```

## Sicherheitsprinzipien

- Prometheus und Exporter niemals direkt ins Internet stellen.
- Grafana-Adminpasswort ausschließlich verschlüsselt speichern.
- Keine Secrets in Metriklabels oder Dashboardvariablen aufnehmen.
- `/metrics` bei einem separaten Server nur für explizite Monitoring-CIDRs erlauben.
- Grafana-Datenbank und Vault getrennt sichern.
- Änderungen mit Syntaxcheck und `promtool` validieren.
- Monitoring-Ausfälle dürfen API und Frontend nicht blockieren.
