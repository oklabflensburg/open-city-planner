# Benachrichtigungssystem

Das Benachrichtigungssystem übersetzt fachliche Ereignisse in persönliche, persistente Hinweise. Es ist bewusst vom Auditlog getrennt: Das Auditlog dokumentiert administrative Nachvollziehbarkeit, während `notifications` ausschließlich die adressierbare Benutzerkommunikation mit gelesenem Zustand, Präferenzen und Aktionsziel abbildet.

## Datenmodell

- `notifications`: Empfänger, optionaler Akteur, Ereignistyp, Kategorie, Priorität, kontrollierter Text, Ressourcenbezug, internes Aktionsziel, gelesen/ungelesen, Ablauf- und Deduplizierungsdaten
- `notification_preferences`: kontoweite Themenpräferenzen; sicherheitsrelevante Kontohinweise bleiben serverseitig aktiv
- `notification_subscriptions`: explizites Folgen einer generisch bezeichneten Ressource mit optionaler Ereignisauswahl

Migration: `20260817_0022_notifications`. PostgreSQL-Indizes optimieren Empfänger-Zeitachse, ungelesene Zähler und Deduplizierung.

## Ereignisse und Policy

`backend/app/services/notification_policy.py` enthält die zentrale Taxonomie und die einzige Übersetzung von Fachereignissen in Kategorie, Priorität, neutralen Text und erlaubte interne Route. Derzeit unterstützt sind:

- GIS: Fläche geändert, gelöscht, aus OSM übernommen oder Status geändert
- OSM und Daten: wesentliche Änderungen an technischen Datenquellen
- Konto/Administration: Rolle vergeben oder entfernt, Konto deaktiviert oder reaktiviert
- Import: abgeschlossen oder fehlgeschlagen

Die Fachservices bestimmen Empfänger aus Eigentümerschaft, Abonnement oder Superuser-Rolle. Gewöhnliche eigene Änderungen werden unterdrückt. Gleichartige Ereignisse derselben Ressource und desselben Empfängers werden innerhalb von fünf Minuten zusammengeführt; `occurrence_count` hält die Anzahl fest.

## API und Realtime

Alle Endpunkte liegen unter `/api/v1/notifications` und verwenden die bestehende Cookie-Authentifizierung. Schreibzugriffe sind CSRF-geschützt.

- `GET /notifications`, `GET /notifications/unread-count`
- `PATCH /notifications/{id}/read`, `POST /notifications/read-all`
- `GET|PATCH /notifications/preferences`
- `GET|PUT|DELETE /notifications/subscriptions`
- `GET /notifications/stream` als Server-Sent-Events

PostgreSQL bleibt die Zustellquelle. Der prozesslokale SSE-Broker liefert neue Einträge verzögerungsarm an den richtigen Empfänger; nach Verbindungsabbruch, Wiederanmeldung oder erneutem Fokus lädt das Frontend den persistenten Stand nach. Für einen Betrieb mit mehreren Backend-Prozessen kann die Fan-out-Schicht später durch PostgreSQL `LISTEN/NOTIFY` oder Redis Pub/Sub ersetzt werden, ohne das Datenmodell oder die API zu ändern.

## Aufbewahrung und Betrieb

Der gemeinsame Deployment-, Neustart- und Rollback-Ablauf ist im
[Deployment- und Betriebsleitfaden](deployment.md) beschrieben.

`NOTIFICATION_RETENTION_DAYS` legt die reguläre Aufbewahrung fest und beträgt standardmäßig 90 Tage. Die Bereinigung läuft bewusst nicht in API-Requests. Ein täglicher Cron- oder systemd-Timer kann folgenden begrenzten One-shot-Job starten:

```bash
cd backend
.venv/bin/python -m app.cli.cleanup_notifications
```

Explizit abgelaufene Einträge werden entfernt. Alte ungelesene `ACTION_REQUIRED`-Hinweise bleiben erhalten, bis sie gelesen oder über `expires_at` beendet wurden. Der Job protokolliert ausschließlich die Anzahl gelöschter Zeilen und keine personenbezogenen Inhalte.

## Frontend

Der Pinia-Store `frontend/app/stores/notifications.ts` führt Liste, ungelesenen Zähler, optimistische Lesezustände, Präferenzen, Abonnements, SSE-Reconnect und globale Toasts zusammen. Die Glocke verwendet am Desktop ein Popover und mobil das bestehende Bottom-Sheet-Muster. Nur Erfolgs-, Fehler- und handlungsrelevante Ereignisse erzeugen einen Toast; gleichzeitig sind höchstens drei sichtbar.

Aktionslinks werden sowohl in der Backend-Policy als auch vor der Navigation im Frontend auf interne Pfade begrenzt. Die UI kennzeichnet ungelesene Einträge semantisch und stellt Status nicht ausschließlich über Farbe dar.

## Neue Ereignisse ergänzen

1. Ereignistyp im Enum `NotificationEventType` ergänzen.
2. Kontrollierte Darstellung und Route in `NotificationPolicy.render` definieren.
3. Im zuständigen Fachservice nach erfolgreicher fachlicher Änderung Empfänger ermitteln, Benachrichtigungen in derselben Transaktion erzeugen und erst nach dem Commit veröffentlichen.
4. Empfänger-, Datenschutz-, Deduplizierungs- und UI-Tests ergänzen.

Freitext aus externen Quellen, Secrets und interne Fachdaten dürfen nicht direkt als Benachrichtigungstext oder Aktions-URL übernommen werden.
