# Sicherheitscheckliste für den Produktivbetrieb

## Erforderliche Anwendungseinstellungen

- [ ] `APP_ENVIRONMENT=production` ist gesetzt.
- [ ] `AUTH_COOKIE_SECURE=true` sowie eine geeignete Cookie-Domain und ein geeigneter Cookie-Pfad sind konfiguriert.
- [ ] `REQUIRE_MFA_FOR_SUPERUSERS=true` ist gesetzt.
- [ ] `REFRESH_REQUIRE_ORIGIN=true` ist gesetzt.
- [ ] `AUTH_RATE_LIMIT_BACKEND=redis` ist gesetzt.
- [ ] `RATE_LIMIT_FAIL_CLOSED=true` ist gesetzt.
- [ ] `REDIS_ENABLED=true` ist gesetzt, und Redis ist erreichbar, bevor Anfragen freigeschaltet werden.
- [ ] `JWT_ALGORITHM=HS256` sowie die erwarteten Werte für `JWT_ISSUER` und `JWT_AUDIENCE` sind konfiguriert.
- [ ] Voneinander unabhängige und zufällig erzeugte Werte für `JWT_SECRET_KEY`, `OAUTH_STATE_SECRET`, `MFA_RECOVERY_PEPPER` und `MFA_ENCRYPTION_KEY` werden aus der Geheimnisverwaltung eingebunden.
- [ ] `CORS_ORIGINS`, `APP_BASE_URL`, `API_BASE_URL`, die OAuth-Callback-Adressen, `WEBAUTHN_ORIGIN` und `WEBAUTHN_RP_ID` stimmen exakt mit den öffentlich verwendeten Ursprüngen überein.
- [ ] `TRUSTED_PROXIES` enthält ausschließlich die tatsächlich eingesetzten Reverse-Proxy-Adressen beziehungsweise CIDR-Netze. Andernfalls bleibt die Einstellung leer.

Das Backend verweigert den Start bewusst, wenn zentrale Sicherheitsvorgaben für die Produktion fehlen. Die dokumentierten Entwicklungswerte dürfen nicht für eine Produktivumgebung übernommen werden.

## Netzübergang und Infrastruktur

- [ ] Weiterleitungen auf HTTPS sind aktiv. HSTS wird ausgeliefert, nachdem der ausschließliche HTTPS-Betrieb für alle Endpunkte sichergestellt wurde.
- [ ] CSP und die übrigen Sicherheitsheader werden vom Proxy oder CDN unverändert weitergegeben.
- [ ] PostgreSQL und Redis sind nicht öffentlich erreichbar. Soweit von der Plattform unterstützt, werden authentifizierte und verschlüsselte Verbindungen verwendet.
- [ ] Die Datenbankrolle der Anwendung besitzt nur die erforderlichen Berechtigungen. Zugangsdaten für Migrationen werden, soweit praktikabel, getrennt verwaltet.
- [ ] API- und Hintergrundprozesse laufen unter Benutzern ohne erhöhte Systemrechte.
- [ ] Firewall- und ausgehende Netzwerkregeln erlauben ausschließlich die benötigten OAuth-, E-Mail-, Karten-, Daten- und Mastodon-Ziele.

Beispiel für grundlegende Nginx-Grenzwerte und -Header; die erlaubten Ursprünge müssen vor der Verwendung an den jeweiligen Host angepasst werden:

```nginx
client_max_body_size 6m;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

Die Anwendung setzt ihre eigenen Größenlimits auch dann durch, wenn `Content-Length` fehlt oder einen falschen Wert enthält. Das Proxy-Limit sollte etwas oberhalb der konfigurierten Avatargröße zuzüglich des Multipart-Overheads liegen. Es darf nicht als einzige Schutzmaßnahme verwendet werden.

## Daten und Betrieb

- [ ] Vor dem Start des neuen Backends wurden `app.cli.module_migrations preflight` und `upgrade` ausgeführt und der einzelne globale Migration-Head geprüft.
- [ ] Die Redis-Konfiguration für Persistenz und Verdrängung eignet sich für Sicherheitszähler. Das konfigurierte Präfix ist für jede Umgebung eindeutig.
- [ ] Automatisierte und verschlüsselte Sicherungen der Datenbank und Geheimnisse sind vorhanden. Wiederherstellungstests sind geplant und die Aufbewahrungsdauer ist dokumentiert.
- [ ] Protokolle sind zugriffsgeschützt, werden rotiert und enthalten keine vertraulichen Werte. Tokens, Passwörter, MFA-Werte, OAuth-Codes und Autorisierungsheader gelangen nicht in die Protokolle.
- [ ] Die Überwachung alarmiert bei ungewöhnlich vielen Anmeldungen, Ausfällen des Limitierungsdienstes, wiederverwendeten Aktualisierungstokens, wiederholten MFA-Fehlern und erhöhten Datenbank-Zeitüberschreitungen.
- [ ] Abhängigkeitsprüfungen, Sicherheitstests und Anwendungstests laufen in der CI-Pipeline. Kritische Sicherheitshinweise verhindern eine Bereitstellung.
- [ ] Für Betriebssystem, Python, Node.js, Datenbank, Redis, Proxy und Container gilt ein festgelegter Aktualisierungsrhythmus.

## Prüfung vor der Veröffentlichung

- [ ] Backend-Tests und Ruff sind erfolgreich.
- [ ] Frontend-Tests, Typprüfung und Produktions-Build sind erfolgreich.
- [ ] Die bestehenden Playwright-Tests sind in einer isolierten Umgebung erfolgreich.
- [ ] Release Gate, Backend-/Frontend-Dependency-Audits, CodeQL-SAST,
      Gitleaks und Security-Exception-Validierung sind für den Release-Commit grün.
- [ ] Anmeldung, OAuth mit MFA, Passwortzurücksetzung, Abmeldung nach Passwortänderung, Rotation der Aktualisierungstokens, Admin-MFA und verifizierte GIS-Schreibzugriffe wurden durch Funktionstests geprüft.
- [ ] Die Sicherheitsheader wurden anhand der tatsächlich öffentlich ausgelieferten Frontend- und API-Antworten geprüft.
