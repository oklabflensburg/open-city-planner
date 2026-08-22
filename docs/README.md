# Technische Dokumentation

Dieses Verzeichnis enthält die Entwickler-, Architektur- und Betriebsdokumentation des Stadtplaners. Das öffentliche Benutzerhandbuch wird im Frontend aus `frontend/app/config/documentation.ts` erzeugt und ist unter `/dokumentation` erreichbar.

## Einstieg

- [Projektüberblick und lokales Schnellsetup](../README.md)
- [Beiträge zum Projekt](../CONTRIBUTING.md)
- [Backend-Entwicklung](../backend/README.md)
- [Frontend-Entwicklung](../frontend/README.md)
- [Sprachleitfaden](language-style-guide.md)

## Architektur und Frontend

- [Frontend-Design und Analyse](frontend-design.md)
- [Reihenfolge der GIS-Layer](map-layer-order.md)
- [Intelligente Suche](intelligent-search.md)
- [Stadtplaner-Assistent](stadtplaner-assistant.md)
- [Benachrichtigungssystem](notifications.md)
- [E-Mail-Vorlagen und Outbox](email-templates.md)
- [Externe Anbieter-Icons](provider-icons.md)

## GIS, OpenStreetMap und Gebiete

- [Lokale OpenStreetMap-Daten](osm-data.md)
- [Stündliche OpenStreetMap-Synchronisierung](osm-hourly-sync.md)
- [Wikidata-Anreicherung von Gebieten](wikidata-enrichment.md)
- [Kartenperformance](map-performance.md)
- [Analytics-Query-Plan prüfen](analysis-area-analytics-performance.md)

## Statistik und Daten

- [Kommunale Statistik aus dem Flensburger Zahlenspiegel](flensburg-statistics.md)
- [Redis-Read-Cache und Invalidierung](redis-cache.md)

## Betrieb und Integrationen

- [Deployment und Betrieb](deployment.md)
- [Wiederholbares Ansible-Deployment](../deploy/ansible/README.md)
- [Nginx-Hardening und Rate Limits](../deploy/nginx/README.md)
- [Social Publishing mit Mastodon](social-publishing.md)
- [Produktions-Sicherheitscheckliste](security/production-checklist.md)
- [Zwei-Faktor-Authentifizierung](security/mfa.md)
- [Passkeys und WebAuthn](security/passkeys.md)

## Qualität und Performance

- [Dokumentationsaudit und Wartungsregeln](documentation-audit.md)
- [Continuous Integration](ci.md)
- [Frontend-Build und Bundle-Grenzen](frontend-build-performance.md)
- [Performance-Audit vom 16. August 2026](performance-audit-2026-08-16.md)

## Wartungsregeln

Eine neue sichtbare Kernfunktion benötigt:

1. einen verständlichen Eintrag im öffentlichen Benutzerhandbuch;
2. technische Dokumentation, wenn Architektur, Datenfluss oder Betrieb nicht selbsterklärend sind;
3. passende Suchbegriffe in `documentation.ts`;
4. Tests für neue Slugs, Navigation und zentrale Suchbegriffe.

Änderungen an Environment-Variablen, CLI-Befehlen, Rollen, Routen oder systemd-Units müssen gleichzeitig in den betroffenen Dokumenten aktualisiert werden. Die Dateien `.env.example`, die Pydantic-Settings, die tatsächlichen CLI-Module und `deploy/systemd/` sind dabei maßgeblich.
- [Polygon API: Konsistenzmodell & Outbox](polygon-consistency.md)
