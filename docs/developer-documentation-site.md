# Öffentliche Entwicklerdokumentation

Die technische Dokumentation wird auf zwei Ebenen gepflegt:

- `developer.stadtplaner.oklabflensburg.de` bietet einen kuratierten, navigierbaren Einstieg für Entwickler und Betreiber.
- `docs/` im Repository bleibt die vollständige implementierungsnahe technische Source of Truth.

## Warum eine eigene Subdomain?

Die öffentliche Hilfe unter `stadtplaner.oklabflensburg.de/dokumentation` richtet sich an Nutzer des GIS. Technische Inhalte zu PostGIS, OSM-Synchronisation, Groq, CI, Performance und Deployment würden diese Navigation unnötig überladen. Die Subdomain trennt Zielgruppen, verwendet aber weiterhin dieselbe Nuxt-Anwendung und dasselbe Designsystem.

## Routing

Die Anwendung kennt weiterhin die internen Routen unter `/dokumentation/entwickler`. Eine globale Nuxt-Middleware ordnet die produktive Entwickler-Subdomain diesen Seiten zu. Auf der Hauptdomain wird ein Aufruf des Entwicklerpfads dauerhaft auf die kanonische Entwickler-Subdomain weitergeleitet.

Lokale Entwicklung bleibt unter `/dokumentation/entwickler` möglich, weil die Host-Weiterleitung nur für die produktiven Hostnamen greift.

## DNS und Reverse Proxy

DNS und TLS werden außerhalb des Repositorys verwaltet. Für `developer.stadtplaner.oklabflensburg.de` muss ein DNS-Eintrag auf denselben Webserver zeigen. Der Reverse Proxy kann denselben Nuxt-Upstream wie die Hauptseite verwenden und muss den ursprünglichen `Host`-Header weiterreichen, damit die Nuxt-Middleware die Subdomain erkennt.

Beispielhaft:

```nginx
server {
    server_name developer.stadtplaner.oklabflensburg.de;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Dieses Beispiel ersetzt keine bestehende produktive TLS-, Security-Header- oder Proxy-Konfiguration.

## Inhalt

Die Entwicklerseite enthält kuratierte Einstiege zu:

- Architektur
- API und Backend
- OpenStreetMap und GIS
- kommunaler Statistik
- intelligenter Suche und Assistant
- CI und Tests
- Deployment und Betrieb

Spezialdokumente wie SQL-Explain-Dateien, Performance-Audits und tiefgehende Sync-/Recovery-Dokumente bleiben im Repository und werden von der Entwicklerseite aus verlinkt.

## SEO

Entwicklerseiten verwenden `https://developer.stadtplaner.oklabflensburg.de` als kanonische Origin. Die Hauptdomain soll für dieselben technischen Inhalte keine konkurrierenden Canonical-URLs erzeugen.

## Sicherheit

Die Entwicklerdokumentation ist öffentlich, enthält aber keine Secrets. Architektur, Frameworks und öffentliche API-Verträge dürfen beschrieben werden. Nicht veröffentlicht werden echte API-Keys, Datenbankpasswörter, Tokens, private Nutzer-/Eigentümerdaten oder vertrauliche Produktionskonfigurationen.

## Betrieb

Die zentrale Betriebsreferenz ist `docs/deployment.md`. DNS, TLS und die produktive Reverse-Proxy-Konfiguration sind serverseitige Voraussetzungen und können durch einen Repository-Commit allein nicht aktiviert werden.
