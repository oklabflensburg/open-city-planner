# Social Publishing mit Mastodon

Stadtplaner veröffentlicht optional kontrollierte Hinweise zu öffentlichen Änderungen über die Mastodon-REST-API. Mastodon übernimmt die ActivityPub-Föderation; die Anwendung betreibt keinen eigenen ActivityPub-Actor.

## Abgrenzung und Sicherheit

- Die Integration ist standardmäßig deaktiviert.
- `MASTODON_ACCESS_TOKEN` bleibt ausschließlich im Backend-Environment.
- Zulässig sind nur kontrollierte öffentliche Felder und Vorlagen.
- Eigentümer-, Miet-, Benutzer-, Authentifizierungs- und interne Verwaltungsdaten sind ausgeschlossen.
- Das Token benötigt für Veröffentlichungen nur die tatsächlich verwendeten Mastodon-Berechtigungen für Status und Medien.
- `MASTODON_DRY_RUN=true` erzeugt Vorschau und Historie, sendet aber keinen Beitrag.

Mastodon-SSO ist davon getrennt. `MASTODON_SSO_*` dient der Benutzeranmeldung und verwendet niemals das Publishing-Token.

## Outbox und Publisher

Gebietsänderung und Outbox-Ereignis werden gemeinsam in PostgreSQL gespeichert. Der One-shot-Worker verarbeitet fällige Einträge unabhängig vom auslösenden HTTP- oder Importvorgang:

```bash
cd backend
.venv/bin/python -m app.cli.publish_social_outbox --limit 20
.venv/bin/python -m app.cli.mastodon_status
```

Die mitgelieferten Units `stadtplaner-social-publisher.service` und `.timer` starten den Worker regelmäßig. Temporäre Netzwerkfehler, HTTP 429 und Serverfehler werden begrenzt mit Backoff wiederholt. Jeder Eintrag besitzt einen stabilen Idempotency-Key.

## Veröffentlichungspolitik

- Gleichartige Gebietsänderungen werden innerhalb des konfigurierten Zeitfensters gebündelt.
- Der reguläre OSM-Sync erzeugt keine Social-Ereignisse. Nur ein bewusst mit `--publish-relevant-updates` gestarteter Gebietssync darf passende Änderungen einreihen.
- Eine aus OSM übernommene Stadtplaner-Fläche kann genau ein Adoption-Ereignis erzeugen. Spätere Autosaves erzeugen keine Wiederholung.
- Ein Statistikimport erzeugt bei tatsächlichen Änderungen höchstens einen zusammenfassenden Hinweis.
- Löschungen, technische Cache- oder Zeitstempeländerungen sowie Login-, Audit- und Rollenereignisse werden nicht automatisch veröffentlicht.

Automatische Beiträge enthalten einen Screenshot einer serverseitig bestimmten öffentlichen Route und einen deterministischen Alternativtext. Adminseiten und beliebige URLs aus Event-Payloads werden nicht geöffnet. Schlägt der Pflicht-Screenshot fehl, wird kein reiner Textbeitrag gesendet.

## Administration und Betrieb

Superuser sehen unter `/admin/social` Verbindungsstatus, Einstellungen, Vorschau, Warteschlange und Veröffentlichungshistorie. Tokens und Authorization-Header sind niemals Teil der API-Antwort.

Die Aktivierung und systemd-Installation ist in [Deployment und Betrieb](deployment.md) beschrieben. Die vollständige Variablenliste steht in `backend/.env.example`.
