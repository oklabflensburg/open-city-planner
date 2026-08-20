# E-Mail-Vorlagen

Das E-Mail-System verwendet ein zentrales Register in `backend/app/services/email_service.py`. Dieses Register ist die verbindliche Liste aller zulässigen Vorlagen und enthält deren deutsche Bezeichnung, Kategorie, Standardbetreff, HTML- und Textinhalt, erlaubte Variablen sowie Sicherheitsstatus.

## Registrierte Vorlagen

| Schlüssel | Zweck | Status |
| --- | --- | --- |
| `verify_email` | E-Mail-Adresse bestätigen | aktiv |
| `password_reset` | Passwort zurücksetzen | aktiv |
| `password_changed` | Passwortänderung bestätigen | aktiv |
| `mfa_security` | MFA-, Wiederherstellungs- und Passkey-Ereignisse | aktiv |
| `contact_notification` | interne Kontaktbenachrichtigung | aktiv |
| `contact_copy` | Kopie an den Absender | aktiv |
| `welcome` | Willkommensmail nach bestätigter Konto-E-Mail | aktiv |
| `system_announcement` | Layout für System- und Rundmitteilungen | aktiv |
| `notification_email` | optionale E-Mail zu einer Benachrichtigung | aktiv |

Unbekannte Schlüssel werden abgelehnt. Neue Mailarten müssen zuerst im Register angelegt und anschließend über den zentralen Renderer versendet werden.

## Standard und Datenbank-Override

Ohne Datenbankeintrag wird immer der im Repository hinterlegte Standard verwendet. Die Migration `20260819_0029` legt die Tabelle `email_templates` an. Sie speichert nur die aktuelle bearbeitbare Fassung, Anpassungsstatus, Version und letzten Bearbeiter. Ein Deployment benötigt deshalb kein Seeding.

Änderungen verwenden optimistische Versionierung. Stimmt die übermittelte Version nicht mehr, antwortet die API mit `409 EMAIL_TEMPLATE_VERSION_CONFLICT`. „Standard wiederherstellen“ schreibt die Registry-Werte zurück und kennzeichnet die Vorlage als nicht angepasst.

## Unveränderliches Layout und Rechtstexte

`backend/app/templates/email/base.html` umschließt jeden administrierbaren HTML-Inhalt. Der Superuser kann weder Logo noch Header, Footer, Impressum oder Datenschutz entfernen. Textmails erhalten denselben rechtlichen Footer serverseitig.

Die globalen Werte werden aus `APP_BASE_URL` erzeugt:

- Logo: `${APP_BASE_URL}/branding/ok-lab-flensburg-email.png`
- Impressum: `${APP_BASE_URL}/impressum`
- Datenschutz: `${APP_BASE_URL}/datenschutz`

Im Produktionsbetrieb muss `APP_BASE_URL` eine absolute HTTPS-Origin ohne Pfad, Query oder Fragment sein. Das Logo ist ein lokales PNG ohne Drittanbieteraufruf oder Tracking.

## Variablen und Sandbox

Jede Vorlage besitzt eine eigene Variablen-Allowlist. In der Admin-Oberfläche werden die erlaubten und verpflichtenden Variablen angezeigt. An den Renderer werden ausschließlich einfache Zeichenketten übergeben, niemals Benutzer-, Request-, Session- oder Settings-Objekte.

Administrierbare Inhalte laufen durch eine `SandboxedEnvironment` mit `StrictUndefined`. Funktionsaufrufe, Attribute, Indizes, Filter, Tests, Includes, Imports, Makros, Zuweisungen und Schleifen sind gesperrt. Unbekannte Variablen erzeugen `422 EMAIL_TEMPLATE_VARIABLE_NOT_ALLOWED`.

Die sicherheitskritischen Vorlagen `verify_email` und `password_reset` müssen ihre serverseitig erzeugte Aktionsvariable sowohl im HTML- als auch im Textinhalt behalten. Vorschauen verwenden ausschließlich Werte unter `example.invalid` und erzeugen keine realen Token.

## HTML-Bereinigung

Erlaubt sind `p`, `br`, `strong`, `em`, `ul`, `ol`, `li`, `h1`, `h2`, `h3`, `a` und `blockquote`. Skripte, Styles, Formulare, eingebettete Inhalte, SVG/MathML, Event-Handler und nicht erlaubte Attribute werden entfernt. Links sind auf HTTPS, `mailto` und im Entwicklungsbetrieb HTTP begrenzt. `javascript:`, `data:` und `file:` sind nicht zulässig.

Die kontrollierte Klasse `email-button` wird serverseitig in festes mailclient-taugliches Inline-CSS überführt. Freies CSS ist nicht möglich.

## Admin-Verwaltung

Der Menüpunkt „E-Mail-Vorlagen“ erscheint ausschließlich für Superuser. Alle Endpunkte liegen unter `/api/v1/admin/email-templates`, verwenden die bestehende Superuser- und MFA-Policy und liefern `Cache-Control: private, no-store`.

- `GET /` – Übersicht
- `GET /{key}` – Detail
- `PATCH /{key}` – Änderung mit CSRF und Version
- `POST /{key}/preview` – isolierte serverseitige Vorschau
- `POST /{key}/test-send` – Testmail nur an die eigene Superuser-Adresse, höchstens fünfmal in zehn Minuten
- `POST /{key}/reset` – Registry-Standard wiederherstellen

Die Vorschau wird im Frontend in einem leeren `sandbox`-Iframe angezeigt und nicht mit `v-html` in das Administrationsdokument eingefügt.

## Audit und Betrieb

Änderungen, Zurücksetzungen und Testsendungen erzeugen `EMAIL_TEMPLATE_UPDATED`, `EMAIL_TEMPLATE_RESET` beziehungsweise `EMAIL_TEMPLATE_TEST_SENT`. Im Auditlog stehen nur Schlüssel, Version und geänderte Feldnamen, niemals vollständige Inhalte oder Token.

SMTP bleibt intern synchron, wird aus der asynchronen Renderpipeline aber über `asyncio.to_thread` aufgerufen und blockiert daher keine FastAPI-Request-Schleife. Das Console-Backend protokolliert weder Empfänger noch Mailinhalt.

## E-Mail-Zentrale und Rundmails

Der Adminbereich bündelt unter „E-Mail-Zentrale“ die bestehenden Vorlagen, Rundmail-Entwürfe und den Versandstatus. Eine Rundmail ist ein eigener, versionierter Datensatz und verändert die globale Vorlage `system_announcement` nicht. Speichern, Vorschau und Testmail starten keinen Massenversand. Erst der ausdrücklich bestätigte Start legt die Empfänger fest und erzeugt pro Empfänger eine Zustellung.

Die Migration `20260819_0031` ergänzt `email_campaigns`, `email_campaign_deliveries` und `email_unsubscribe_tokens`. Nach dem Start ist der Inhalt einer Kampagne unveränderlich. Die Zustellungstabelle hält E-Mail-Adresse und Anzeigename als Versand-Snapshot fest; gelöschte Konten können per `SET NULL` von ihrer Zustellung getrennt werden. Eine geplante Kampagne wird erst beim ersten fälligen Worker-Claim auf `PROCESSING` gesetzt.

Zielgruppen sind alle aktiven Konten, bestätigte Konten oder Superuser. Für `NEWSLETTER` werden ausschließlich Konten mit ausdrücklichem Opt-in berücksichtigt. `LEGAL` ignoriert den Newsletter-Schalter, benötigt aber eine zusätzliche Bestätigung und ein eigenes Auditereignis. `SERVICE` und `SYSTEM` sind in dieser ersten Fassung als notwendige betriebliche Kommunikation klassifiziert und berücksichtigen den Newsletter-Schalter ebenfalls nicht. Diese technische Einordnung ersetzt nicht die rechtliche Prüfung des konkreten Inhalts; freiwillige redaktionelle Inhalte müssen als `NEWSLETTER` versendet werden.

## Mehrkanal-Benachrichtigungen

Die vorhandenen Kategorien GIS, OpenStreetMap, Gebiete/Daten, Social und System steuern nun getrennt den In-App- und den optionalen E-Mail-Kanal. `email_enabled` ist der globale E-Mail-Schalter; die Felder `email_notify_gis`, `email_notify_osm`, `email_notify_area_updates`, `email_notify_social` und `email_notify_system` steuern die Kategorien. `newsletter_enabled` bleibt davon unabhängig. Alle neuen E-Mail-Schalter sind für bestehende und neue Konten standardmäßig deaktiviert, damit ein Deployment keine unerwartete Mailflut auslöst.

Die Notification Policy entscheidet mit `email_eligible`, welche Ereignisse überhaupt als E-Mail geeignet sind. Derzeit sind wesentliche GIS-Statusänderungen und Löschungen, wesentliche OSM-Änderungen, aktualisierte Gebietsstatistiken, fehlgeschlagene oder freizugebende Social-Veröffentlichungen sowie fehlgeschlagene Importe zugelassen. Kleine GIS-Aktualisierungen bleiben In-App. Persistente Notification-ID und eindeutiger Outbox-Schlüssel begrenzen die Zustellung auf höchstens eine E-Mail je Benachrichtigung.

Konto- und Sicherheitsmails wie Verifikation, Passwort-Reset sowie MFA- und Passkey-Hinweise verwenden weiterhin ihre bestehende, verpflichtende Zustelllogik. Sie sind weder vom Newsletter- noch vom optionalen Benachrichtigungsschalter abhängig.

## Allgemeine E-Mail-Outbox

Die Willkommensmail wird nicht bei der Registrierung versendet. Die erfolgreiche E-Mail-Bestätigung setzt `users.is_verified` und legt in derselben Datenbanktransaktion genau einen Outbox-Eintrag für den Benutzer an. Erst nach diesem Commit wird ein unmittelbarer Versandversuch gestartet. Ein SMTP-Fehler kann den bestätigten Kontostatus deshalb nicht zurückrollen.

Neue OAuth-Konten werden nur dann unmittelbar eingereiht, wenn der Provider sowohl eine E-Mail-Adresse als auch deren bestätigten Status liefert. Konten mit ausstehender E-Mail-Adresse erhalten die Nachricht erst nach der späteren Bestätigung. `email_outbox` besitzt nun einen eindeutigen `idempotency_key`: `welcome:{user_id}`, `campaign:{campaign_id}:{user_id}` oder `notification:{notification_id}:email`. Zusammen mit `users.welcome_email_sent_at` bleibt die Willkommensmail genau einmal eingeplant und nach erfolgreicher Zustellung dauerhaft markiert. Worker beanspruchen fällige Einträge mit einer Zeilensperre und `SKIP LOCKED`.

Fehlgeschlagene temporäre Versuche bleiben mit begrenztem exponentiellem Abstand retryfähig; die maximale Versuchszahl wird über `EMAIL_OUTBOX_MAX_ATTEMPTS` konfiguriert. Permanente Empfängerfehler enden als `FAILED`. Die Outbox speichert weder Verifikations- noch Passwort-Reset-Token, TOTP-Geheimnisse oder Wiederherstellungscodes. Noch nicht versendete Kampagneneinträge können auf `CANCELLED` gesetzt werden.

Newsletter enthalten einen zufälligen, nur gehasht gespeicherten Abmeldetoken sowie `List-Unsubscribe` und `List-Unsubscribe-Post`. Die öffentliche Route `/email-abmelden` deaktiviert ausschließlich `newsletter_enabled`, funktioniert ohne Anmeldung idempotent und zeigt keine Kontodaten. Ein erneutes Opt-in erfolgt nur im eingeloggten Profil. Optionale Notification-Mails verlinken stattdessen auf die Einstellungen nach Anmeldung.

Der periodische One-shot-Worker verarbeitet fällige Einträge unabhängig vom ursprünglichen Request:

```bash
cd backend
.venv/bin/python -m app.cli.process_email_outbox --limit 20
```

Für systemd stehen `deploy/systemd/stadtplaner-email-outbox.service` und `.timer` bereit. Auditereignisse enthalten nur Outbox-ID und Versuchszahl, niemals Empfänger, Mailinhalt oder Template-Kontext.

Der gemeinsame Ablauf für Migration, Build, Neustart, Smoke-Tests und Rollback
steht im [Deployment- und Betriebsleitfaden](deployment.md). Für das E-Mail-System
sind zusätzlich zu prüfen:

1. `APP_BASE_URL` auf die öffentliche Frontend-Origin setzen, produktiv beispielsweise `https://stadtplaner.oklabflensburg.de`.
2. `alembic upgrade head` im Backend ausführen.
3. Die zum auszurollenden Commit gehörenden Units `stadtplaner-email-outbox.service` und `.timer` installieren und den Timer aktivieren. Derselbe Worker verarbeitet Welcome-, Notification- und Kampagnenmails.
4. Backend und Frontend neu bauen und neu starten.
5. Erreichbarkeit von Logo, Impressum und Datenschutz über die öffentliche Domain prüfen.

Inhaltliche Anpassungen können pro Vorlage über „Standard wiederherstellen“
zurückgenommen werden. Schema-Downgrades sind kein pauschaler
Anwendungs-Rollback: Sie können Outbox-, Kampagnen- und Vorlagendaten verlieren
und dürfen nur nach Prüfung der konkreten Migrationen und mit geprüftem Backup
erfolgen.
