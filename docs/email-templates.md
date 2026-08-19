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

## Willkommensmail und E-Mail-Outbox

Die Willkommensmail wird nicht bei der Registrierung versendet. Die erfolgreiche E-Mail-Bestätigung setzt `users.is_verified` und legt in derselben Datenbanktransaktion genau einen Outbox-Eintrag für den Benutzer an. Erst nach diesem Commit wird ein unmittelbarer Versandversuch gestartet. Ein SMTP-Fehler kann den bestätigten Kontostatus deshalb nicht zurückrollen.

Neue OAuth-Konten werden nur dann unmittelbar eingereiht, wenn der Provider sowohl eine E-Mail-Adresse als auch deren bestätigten Status liefert. Konten mit ausstehender E-Mail-Adresse erhalten die Nachricht erst nach der späteren Bestätigung. `email_outbox` erzwingt für `template_key + user_id` Datenbank-Eindeutigkeit; `users.welcome_email_sent_at` hält den erfolgreichen Versand dauerhaft fest. Parallele Bestätigungsanfragen und Worker können dadurch nicht gleichzeitig dieselbe Nachricht beanspruchen.

Fehlgeschlagene Versuche bleiben mit begrenztem exponentiellem Abstand retryfähig. Die Outbox speichert weder Verifikations- noch Passwort-Reset-Token und rendert den jeweils aktuellen, im Adminbereich gepflegten `welcome`-Inhalt erst beim Versand. Zulässige Variablen sind `name`, `app_url`, `documentation_url` und optional `profile_url`.

Der periodische One-shot-Worker verarbeitet fällige Einträge unabhängig vom ursprünglichen Request:

```bash
cd backend
.venv/bin/python -m app.cli.process_email_outbox --limit 20
```

Für systemd stehen `deploy/systemd/stadtplaner-email-outbox.service` und `.timer` bereit. Auditereignisse enthalten nur Outbox-ID und Versuchszahl, niemals Empfänger, Mailinhalt oder Template-Kontext.

Vor dem Deployment:

1. `APP_BASE_URL` auf die öffentliche Frontend-Origin setzen, produktiv beispielsweise `https://stadtplaner.oklabflensburg.de`.
2. `alembic upgrade head` im Backend ausführen.
3. Die Units `stadtplaner-email-outbox.service` und `.timer` installieren und den Timer aktivieren.
4. Backend und Frontend neu bauen und neu starten.
5. Erreichbarkeit von Logo, Impressum und Datenschutz über die öffentliche Domain prüfen.

Ein Rollback der Anpassungen erfolgt pro Vorlage über „Standard wiederherstellen“. `alembic downgrade 20260819_0029` entfernt die Welcome-Outbox und den Versandzeitpunkt; ein weiterer Downgrade auf `20260819_0028` entfernt sämtliche gespeicherten Overrides.
