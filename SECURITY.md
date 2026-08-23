# Sicherheitsrichtlinie

## Unterstützte Versionen

Sicherheitskorrekturen werden für den aktuellen Stand des Branches `main` bereitgestellt. Derzeit gibt es keine separat gepflegten Release-Branches.

## Sicherheitslücken melden

Bitte veröffentlichen Sie Sicherheitslücken nicht in einem öffentlichen Issue. Nutzen Sie die [Kontaktseite des Stadtplaners](https://stadtplaner.oklabflensburg.de/kontakt) und übermitteln Sie zunächst nur die technischen Angaben, die zur Reproduktion und Bewertung des Problems erforderlich sind. Geben Sie den Verantwortlichen ausreichend Zeit, das Problem zu untersuchen und eine Korrektur bereitzustellen, bevor Sie es veröffentlichen. Greifen Sie bei Sicherheitsuntersuchungen nicht auf Daten anderer Personen zu und speichern Sie solche Daten nicht.

## Automatisierte Sicherheitsprüfungen

Der zentrale Security-Workflow läuft für Pull Requests, jeden Push, manuelle
Aufrufe und montags zeitgesteuert. Das Release Gate ruft denselben Workflow
verpflichtend auf. Er umfasst:

- GitHub Dependency Review als Diff-Prüfung für Pull Requests;
- `pip-audit 2.10.1` gegen den mit `uv export --frozen` aus
  `backend/uv.lock` abgeleiteten Produktionssatz;
- `pnpm audit --prod` gegen das unveränderte `frontend/pnpm-lock.yaml`;
- CodeQL `4.37.8` mit `security-extended` für Python und
  JavaScript/TypeScript;
- Gitleaks `8.30.1` gegen die vollständige Git-Historie, mit vollständig
  redigierter Konsolenausgabe;
- Validierung aller zeitlich begrenzten Ausnahmen und negative Gate-Tests.

CodeQL- und Gitleaks-Ergebnisse werden als SARIF in GitHub Code Scanning
veröffentlicht. Pull Requests aus Forks laufen im normalen `pull_request`-
Kontext und erhalten keine Produktionsgeheimnisse oder privilegierten
Maintainer-Token.

## Schweregrade und Blockierregeln

Critical und High blockieren einen Release. Medium wird innerhalb der regulären
Security-Triage bewertet; Low ist zunächst informativ. Die Werkzeuge werden
folgendermaßen auf diese gemeinsame Policy abgebildet:

- Dependency Review und pnpm: `critical` und `high` blockieren.
- CodeQL: Security Score ab 9,0 ist Critical, ab 7,0 High. SARIF-`error`
  ohne numerischen Score wird vorsorglich als High behandelt.
- Gitleaks: Jeder nicht ausgenommene Fund gilt als High.
- `pip-audit`: Da die Advisory-Quellen nicht durchgängig einen stabilen,
  normalisierten Schweregrad liefern, blockiert vorsorglich jede bekannte
  Schwachstelle.

Critical-Funde werden innerhalb von 24 Stunden triagiert und unverzüglich
behoben oder mitigiert. High-Funde werden innerhalb von drei Werktagen triagiert
und innerhalb von 14 Kalendertagen behoben oder mitigiert. Medium und Low werden
im regulären Wartungszyklus bewertet.

## Befristete Ausnahmen

Ausnahmen stehen ausschließlich in
`.github/security-exceptions.yml`. Ein Eintrag benötigt Finding-/CVE-/Rule-ID,
Scanner, Begründung, verantwortliches Team, Ablaufdatum, Mitigation und
Review-Datum. Er darf nur nach Review durch eine für Security verantwortliche
Maintainerin oder einen verantwortlichen Maintainer gemergt werden. Globale oder
unbefristete Ignore-Regeln sind unzulässig.

Vor Ablauf wird der Fund erneut bewertet, behoben oder über einen neuen Pull
Request mit aktualisierter Begründung befristet verlängert. Fehlende,
doppelte, ungültige oder abgelaufene Einträge lassen den Security-Workflow und
damit das Release Gate fehlschlagen. Der Validator kann lokal ausgeführt werden:

```bash
cd backend
uv sync --frozen --extra security --no-editable
uv run --frozen --extra security python ../scripts/security/validate_security_exceptions.py
```

## Sicherheitsarchitektur

- Zugriffs- und Aktualisierungstokens werden in `HttpOnly`-Cookies gespeichert. Kurzlebige Zugriffs-JWTs sind an einen Aussteller, eine Zielgruppe und einen festgelegten Algorithmus gebunden. Aktualisierungstokens werden regelmäßig ersetzt; serverseitige Sitzungsfamilien erkennen eine Wiederverwendung.
- Änderungen mit Cookie-Authentifizierung verwenden einen doppelten CSRF-Schutz. Das Aktualisieren einer Sitzung erfordert in der Produktion zusätzlich einen exakt erlaubten `Origin`- oder `Referer`-Header.
- Wenn ein starker zweiter Faktor eingerichtet ist, werden Passwort- und OAuth-Anmeldungen zunächst durch eine kurzlebige, einmalig verwendbare serverseitige MFA-Anforderung unterbrochen. OAuth-MFA-Anforderungen verwenden ein eng begrenztes `HttpOnly`-Cookie und erscheinen niemals in Weiterleitungs-URLs.
- TOTP-Geheimnisse werden verschlüsselt gespeichert. Wiederherstellungscodes verwenden einen eigenen HMAC-Pepper, und der OAuth-Status verwendet einen eigenen Schlüssel. Für Passkeys wird ausschließlich öffentliches Schlüsselmaterial gespeichert.
- Superuser-Endpunkte verlangen in der Produktion eine starke aktuelle Authentifizierungsmethode (`otp`, `recovery` oder `webauthn`). Administrative Änderungen erfordern zusätzlich einen gültigen CSRF-Nachweis.
- Öffentliche GIS-Änderungen setzen ein aktives und verifiziertes Benutzerkonto voraus. Eigentums- und Rollenprüfungen erfolgen weiterhin serverseitig.
- Redis stellt in der Produktion atomare und prozessübergreifende Sicherheitslimits bereit. Aufwendige öffentliche Abfragen werden begrenzt, zwischengespeichert und mit einem transaktionslokalen PostgreSQL-Zeitlimit ausgeführt.
- Anfrageinhalte, Passwörter, GeoJSON-Stützpunkte, Beschreibungen und serialisierte Eigenschaften sind größenbegrenzt. Avatar-Dateien durchlaufen weiterhin die validierte Bildneukodierung.
- Private Antworten sowie Authentifizierungs- und Administrationsantworten dürfen nicht zwischengespeichert werden. API und Nuxt setzen unter anderem CSP-, Frame-, Referrer-, MIME-Sniffing- und Cross-Origin-Schutzheader; in der Produktion wird zusätzlich HSTS aktiviert.

## Geheimnisse und Schlüsselwechsel

In der Produktion müssen für `JWT_SECRET_KEY`, `OAUTH_STATE_SECRET`, `MFA_RECOVERY_PEPPER` und `MFA_ENCRYPTION_KEY` voneinander unabhängige, zufällig erzeugte Werte verwendet werden. Diese Werte dürfen niemals in das Repository aufgenommen werden. Tokens, OAuth-Codes, Passwörter, MFA-Werte, Wiederherstellungscodes, CSRF-Werte und Zugangsdaten externer Anbieter dürfen nicht protokolliert werden.

Ein Wechsel von `JWT_SECRET_KEY` macht aktive Browser-Tokens ungültig. Ein Wechsel von `MFA_RECOVERY_PEPPER` macht bestehende Wiederherstellungscodes ungültig und muss daher mit der Erzeugung neuer Codes durch die betroffenen Benutzer abgestimmt werden. Geht `MFA_ENCRYPTION_KEY` verloren, können bestehende TOTP-Einrichtungen nicht mehr verwendet werden. Dieser Schlüssel muss deshalb in die verschlüsselte Sicherung der Geheimnisse aufgenommen werden.

## Anfragelimits und Benutzerermittlung

Wenn Redis für die Sicherheitslimits nicht erreichbar ist, lehnt die Produktionsumgebung geschützte Anfragen bewusst ab. Die Antworten bei Anmeldung und Passwortzurücksetzung vermeiden Rückschlüsse darauf, ob ein Benutzerkonto existiert. Die Registrierung behält aus Kompatibilitätsgründen die bestehende Antwort `EMAIL_ALREADY_REGISTERED` bei. Das damit verbundene Risiko einer Benutzerermittlung wird bewusst akzeptiert und durch strenge Limits pro IP-Adresse und normalisierter E-Mail-Adresse reduziert. Diese Schnittstellenentscheidung sollte erneut bewertet werden, sobald die Kompatibilität sie nicht mehr erfordert.

## Anforderungen an die Bereitstellung

Für jede Umgebung und jede Veröffentlichung ist die [Sicherheitscheckliste für den Produktivbetrieb](docs/security/production-checklist.md) abzuarbeiten. API, Frontend, PostgreSQL und Redis müssen in vertrauenswürdigen Netzen betrieben werden; am öffentlichen Netzübergang ist TLS erforderlich. Datenbankmigrationen müssen vor dem Start der aktualisierten Anwendung ausgeführt werden.
