# Nginx-Konfiguration

Dieses Verzeichnis enthält eine gehärtete, aber bewusst konservative Nginx-Vorlage für den Stadtplaner. Die Dateien sind **Vorlagen**: Vor dem Kopieren immer Diff, lokale Pfade, Zertifikate und Ports prüfen.

## Dateien

- `nginx.conf.example`: projektneutrale Basis für `/etc/nginx/nginx.conf` auf einem Server mit mehreren Projekten.
- `conf.d/stadtplaner-rate-limits.conf`: Stadtplaner-spezifische `limit_req_zone`-Definitionen und die Upgrade-Map für den `http {}`-Kontext.
- `sites-available/stadtplaner.conf`: Frontend, API und `developer.stadtplaner.oklabflensburg.de`.

## Warum die globale nginx.conf nicht Stadtplaner-spezifisch sein sollte

`/etc/nginx/nginx.conf` gilt für alle Projekte auf dem Host. Deshalb enthält die Beispielkonfiguration dort nur gemeinsame Parser-, TLS-, Logging- und Kompressionsdefaults. Die Stadtplaner-Limits liegen separat unter `conf.d/` und werden nur in der Stadtplaner-Site tatsächlich angewendet.

Die bisherige Serverkonfiguration sollte insbesondere an diesen Punkten modernisiert werden:

- TLS 1.0 und TLS 1.1 deaktivieren; nur TLS 1.2/1.3 zulassen.
- `X-XSS-Protection` nicht global setzen; der Header ist veraltet.
- keine globale CSP oder `X-Frame-Options` erzwingen, weil die Anwendungen im Repository bereits eigene Security Header liefern.
- sehr große Header-Puffer (`3m`, `4 x 256k`) auf normale Größen zurückführen; solche Werte erhöhen den Speicherverbrauch pro Verbindung und maskieren problematische Clients.
- Gzip-Level 9 vermeiden; Level 6 ist auf einem Shared Host meist das bessere CPU-/Größen-Verhältnis.
- JPEG/PNG/WebP nicht nochmals mit gzip komprimieren.
- `Connection: upgrade` nicht für jeden Proxy-Request erzwingen.
- `X-Forwarded-Proto` und `X-Forwarded-Host` an die Anwendung weiterreichen.

## CORS

Nginx soll für den Stadtplaner **keine zweite CORS-Implementierung** besitzen. FastAPI konfiguriert `CORSMiddleware` selbst. Dadurch gelten Preflight und eigentliche Antwort aus einer Source of Truth und es entstehen keine doppelten oder widersprüchlichen `Access-Control-*`-Header.

Die produktive Backend-Konfiguration muss `CORS_ORIGINS` bzw. die im Backend verwendeten Origin-Settings korrekt setzen.

## Request-ID, JSON-Logs und Metrics

Der VHost erzeugt am Edge über `$request_id` eine `X-Request-ID` für Nuxt und FastAPI. Das `stadtplaner_json`-Access-Log enthält nur Zeitpunkt, Request-ID, Methode, normalisierten `$uri` ohne Query-String, Status und Laufzeiten; Authorization, Cookies und Request Bodies werden nicht protokolliert.

`/metrics` erlaubt zunächst ausschließlich Loopback. Ergänzen Sie gezielt eine `allow <monitoring-cidr>;`-Zeile und behalten Sie `deny all`; Zugangsdaten gehören nicht in die Vorlage. Die Ansible-Variante nutzt dafür `stadtplaner_metrics_allowed_cidrs`.

## Rate-Limiting-Philosophie

Nginx ist nur der äußere Überlastungsschutz. Fachliche, benutzerbezogene oder sicherheitsrelevante Limits gehören weiterhin in FastAPI/Redis.

Die Vorlage verwendet absichtlich großzügige Grenzen:

| Bereich | Sustained Limit | Burst | Zweck |
| --- | ---: | ---: | --- |
| normale API | 20 Requests/s/IP | 100 | normale Karten- und Datenabrufe nicht behindern |
| API global | 500 Requests/s/VHost | 500 | Notbremse gegen verteilte Last |
| Auth | 5 Requests/s/IP | 20 | äußerer Schutz; Redis/FastAPI bleibt maßgeblich |

Die Werte sind Startwerte, keine universellen Kapazitätsgrenzen. NAT-Gateways können viele legitime Nutzer hinter einer IP bündeln, deshalb sind niedrige Per-IP-Limits für eine öffentliche GIS-API ungeeignet.

### Erst beobachten, dann schärfen

Für die normale öffentliche API empfiehlt sich beim ersten Rollout eine Beobachtungsphase. Dazu temporär in der API-`location` ergänzen:

```nginx
limit_req_dry_run on;
```

Nginx blockiert dann nicht, setzt aber `$limit_req_status` auf Werte wie `REJECTED_DRY_RUN`. Das mitgelieferte `main`-Logformat schreibt diesen Status mit.

Beispielauswertung:

```bash
grep 'limit_req=REJECTED_DRY_RUN' /var/log/nginx/access.log | tail -100
```

Nach einigen Tagen realer Last können die Werte angepasst und `limit_req_dry_run` entfernt werden.

## Installation

Vor Änderungen sichern:

```bash
sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.$(date +%Y%m%d-%H%M%S).bak
sudo cp /etc/nginx/sites-available/stadtplaner /etc/nginx/sites-available/stadtplaner.$(date +%Y%m%d-%H%M%S).bak
```

Projektdateien kopieren:

```bash
sudo cp deploy/nginx/conf.d/stadtplaner-rate-limits.conf /etc/nginx/conf.d/stadtplaner-rate-limits.conf
sudo cp deploy/nginx/sites-available/stadtplaner.conf /etc/nginx/sites-available/stadtplaner
```

Die globale `nginx.conf.example` nicht blind kopieren. Zuerst mit der Konfiguration der anderen Projekte vergleichen. Wenn sie übernommen werden soll:

```bash
sudo diff -u /etc/nginx/nginx.conf deploy/nginx/nginx.conf.example
```

Danach kontrolliert editieren oder ersetzen.

## Developer-Subdomain: DNS und Zertifikat

Vor Aktivierung des TLS-vHosts muss DNS für

`developer.stadtplaner.oklabflensburg.de`

auf den Webserver zeigen.

Da Nginx keine Site mit einem noch nicht vorhandenen Zertifikat laden kann, ist der sichere Ablauf:

1. zunächst nur einen HTTP-Serverblock für `developer.stadtplaner.oklabflensburg.de` anlegen oder den TLS-Block in der Vorlage vorübergehend auskommentieren;
2. `sudo nginx -t && sudo systemctl reload nginx`;
3. Zertifikat mit Certbot ausstellen;
4. vollständigen TLS-vHost aus `stadtplaner.conf` aktivieren.

Beispiel mit dem vorhandenen Nginx-Plugin:

```bash
sudo certbot --nginx -d developer.stadtplaner.oklabflensburg.de
```

Für Frontend und API können die vorhandenen Zertifikate weiterverwendet werden. Es ist nicht nötig, Certbot mit allen Domains des Servers gleichzeitig aufzurufen.

## Validierung vor Reload

Immer zuerst:

```bash
sudo nginx -t
```

Nur bei erfolgreichem Test:

```bash
sudo systemctl reload nginx
```

Danach prüfen:

```bash
curl -I https://stadtplaner.oklabflensburg.de/
curl -I https://api.stadtplaner.oklabflensburg.de/health
curl -I https://developer.stadtplaner.oklabflensburg.de/
```

## Rate-Limit-Monitoring

Das Beispiel-Logformat enthält:

- `request_time`
- `upstream_time`
- `limit_req`

Nützliche Prüfungen:

```bash
grep 'limit_req=REJECTED' /var/log/nginx/access.log | tail -100
grep 'limit_req=REJECTED_DRY_RUN' /var/log/nginx/access.log | tail -100
grep 'limit_req=DELAYED' /var/log/nginx/access.log | tail -100
```

Wenn legitime Kartenaufrufe regelmäßig am Limit liegen, zuerst Caching/Query-Kosten untersuchen und das äußere Limit erhöhen. Eine offene Daten-API sollte nicht künstlich knapp gehalten werden.

## Wichtige Grenzen

Nginx kann nur IP, Pfad, Methode, Verbindung und Trafficrate sehen. Es weiß nicht, ob ein Request einen teuren Datenbankplan, Modulaufrufe oder einen authentifizierten Benutzer betrifft. Deshalb bleiben folgende Regeln im Backend:

- Login-/MFA-Schutz;
- nutzerbezogene Limits;
- Provider- und modulbezogene Limits;
- Request-Body-Verträge;
- Datenbank-Statement-Timeouts;
- Rollen und Berechtigungen.

## Rollback

Bei Problemen die gesicherten Dateien zurückspielen und immer vor Reload testen:

```bash
sudo nginx -t
sudo systemctl reload nginx
```
