# Stadtplaner Flensburg

[![Backend CI](https://github.com/oklabflensburg/open-city-planner/actions/workflows/backend.yml/badge.svg)](https://github.com/oklabflensburg/open-city-planner/actions/workflows/backend.yml)
[![Frontend CI](https://github.com/oklabflensburg/open-city-planner/actions/workflows/frontend.yml/badge.svg)](https://github.com/oklabflensburg/open-city-planner/actions/workflows/frontend.yml)
[![E2E Tests](https://github.com/oklabflensburg/open-city-planner/actions/workflows/e2e.yml/badge.svg)](https://github.com/oklabflensburg/open-city-planner/actions/workflows/e2e.yml)
[![Security](https://github.com/oklabflensburg/open-city-planner/actions/workflows/security.yml/badge.svg)](https://github.com/oklabflensburg/open-city-planner/actions/workflows/security.yml)

![Screenshot Stadtplaner Flensburg](https://raw.githubusercontent.com/oklabflensburg/open-city-planner/main/screenshot_stadtplaner.webp)

Produktionsnaher GIS-Monorepo-Scaffold mit Nuxt 4, TailwindCSS 4, MapLibre, Terra Draw, FastAPI, Cookie-basierter Authentifizierung und PostgreSQL/PostGIS.

## Struktur

- `frontend/` Nuxt 4 GIS-UI mit Filter-Drawer, MapLibre-Karte, Terra-Draw-Polygoneditor und Analysepanel
- `backend/` FastAPI REST API mit SQLAlchemy 2, GeoAlchemy2, Alembic, PostGIS, Argon2id-Passwort-Hashing und JWT/Refresh-Session-Verwaltung

Das offizielle Repository des Stadtplaners ist [oklabflensburg/open-city-planner](https://github.com/oklabflensburg/open-city-planner). Hinweise für Beiträge stehen in [CONTRIBUTING.md](CONTRIBUTING.md). Die im Frontend verwendeten Repository-, Issues- und Beitrags-URLs werden zentral in `frontend/app/config/project.ts` gepflegt.

## Continuous Integration

GitHub Actions prüft Backend, Frontend, Datenbankmigrationen und die wichtigsten
Nutzerwege bei jedem Push und Pull Request. Die Browser-Tests starten dafür eine
frische PostGIS-Datenbank mit reproduzierbaren Testdaten; externe Live-Dienste und
Redis werden nicht benötigt. Netzabhängige Abhängigkeitsaudits laufen getrennt
wöchentlich oder manuell.

Die exakten lokalen Befehle, stabilen Check-Namen und die empfohlene Branch
Protection sind in [docs/ci.md](docs/ci.md) dokumentiert.

## Frontend starten

```bash
cd frontend
cp .env.example .env
pnpm install
pnpm dev
```

Nuxt läuft standardmäßig auf `http://localhost:3000`.

## Backend starten

```bash
cd backend
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Die API läuft auf `http://localhost:8000`, OpenAPI auf `/docs` und ReDoc auf `/redoc`.

## Redis-Cache

Redis ist ein optionaler, gemeinsam genutzter Read-Cache für öffentliche GIS-, OSM- und Analytics-Antworten. PostgreSQL/PostGIS bleibt immer die fachliche Hauptdatenbank. Ein leerer oder nicht erreichbarer Redis-Server verursacht deshalb keinen Datenverlust und bei `REDIS_REQUIRED=false` auch keinen Anwendungsfehler.

Klassische Installation unter Debian/Ubuntu:

```bash
sudo apt update
sudo apt install redis-server
sudo systemctl enable --now redis-server
redis-cli ping
```

Die erwartete Antwort ist `PONG`. Anschließend in `backend/.env` mindestens konfigurieren:

```env
REDIS_ENABLED=true
REDIS_REQUIRED=false
REDIS_URL=redis://127.0.0.1:6379/0
CACHE_PREFIX=stadtplaner:dev
```

Für Produktion muss Redis an localhost oder ein privates Netz gebunden bleiben. Empfohlen sind `protected-mode yes`, Firewall beziehungsweise ACL/Auth sowie ein an den verfügbaren RAM angepasstes `maxmemory` mit `maxmemory-policy allkeys-lru`. Redis wird nicht über Nginx exponiert. Da ausschließlich wiederberechenbare Cachewerte gespeichert werden, sind AOF/RDB nicht erforderlich.

Betrieb und Diagnose:

```bash
redis-cli INFO memory
redis-cli INFO stats
redis-cli DBSIZE
cd backend
.venv/bin/python -m app.cli.cache_status
.venv/bin/python -m app.cli.cache_bump osm
.venv/bin/python -m app.cli.cache_clear --resource analytics:overview
```

Nach einem externen OSM-Import muss `cache_bump osm` ausgeführt werden. Der Boundary-Sync und Änderungen an Polygonen oder Kennzahlen erhöhen ihre persistenten Versionen automatisch. Details, Messwerte und Cache-Key-Schemata stehen in [docs/redis-cache.md](docs/redis-cache.md).

## Mastodon und Fediverse

Stadtplaner implementiert keinen eigenen ActivityPub-Actor. Öffentliche Aktualisierungen werden über die Mastodon-REST-API an den vorhandenen Account [`@oklabflensburg@norden.social`](https://norden.social/@oklabflensburg) gesendet; Mastodon übernimmt anschließend die ActivityPub-Föderation.

Die Integration ist standardmäßig deaktiviert. Ein Mastodon User Token wird ausschließlich im Backend-Environment gespeichert und niemals an Nuxt oder einen öffentlichen API-Endpunkt ausgeliefert:

```env
MASTODON_ENABLED=false
MASTODON_BASE_URL=https://norden.social
MASTODON_ACCESS_TOKEN=
MASTODON_ACCOUNT_URL=https://norden.social/@oklabflensburg
MASTODON_ACCOUNT_HANDLE=@oklabflensburg@norden.social
MASTODON_DEFAULT_VISIBILITY=public
MASTODON_AREA_UPDATES_ENABLED=true
MASTODON_AREA_UPDATE_DEBOUNCE_SECONDS=300
MASTODON_DRY_RUN=true
MASTODON_TIMEOUT_SECONDS=10
MASTODON_HASHTAGS=Flensburg,OpenData,Stadtplaner
MASTODON_MAX_ATTEMPTS=5
MASTODON_BOUNDARY_CHANGE_MIN_RATIO=0.01
MASTODON_SCREENSHOT_DIRECTORY=/data/stadtplaner-social
MASTODON_SCREENSHOT_TIMEOUT_SECONDS=30
```

Für Posts mit dem verpflichtenden Screenshot benötigt das Token die minimalen OAuth-Scopes `write:statuses` und `write:media`. Die optionale Prüfung des konkreten Accounts über `GET /api/v1/accounts/verify_credentials` benötigt nach aktueller Mastodon-API zusätzlich `profile` oder `read:accounts`; ohne diesen Zusatz kann weiterhin veröffentlicht werden, die Adminoberfläche kann den Account aber nicht als „Verbunden“ verifizieren. Unnötige Scopes wie `follow` oder `admin` sollen nicht vergeben werden.

Der Screenshot-Worker verwendet Playwright und Chromium. Nach Installation beziehungsweise Aktualisierung der Backend-Abhängigkeiten muss Chromium einmal für den Service-User installiert werden:

```bash
cd /opt/git/open-city-planner/backend
sudo .venv/bin/python -m playwright install-deps chromium
sudo -u oklab .venv/bin/python -m playwright install chromium
sudo install -d -o oklab -g www-data -m 0770 /data/stadtplaner-social
```

Vor der ersten Produktivaktivierung wird `MASTODON_DRY_RUN=true` empfohlen. Dabei werden kontrollierte Texte und Publication-History erzeugt, aber keine HTTP-Schreibanfrage an Mastodon gesendet. Statusprüfung ohne Tokenausgabe:

```bash
cd backend
.venv/bin/python -m app.cli.mastodon_status
```

Gebietsänderung und Outbox-Ereignis werden in derselben PostgreSQL-Transaktion gespeichert. Ein periodischer One-shot-Worker verarbeitet fällige Ereignisse unabhängig vom ursprünglichen HTTP- oder Importvorgang:

```bash
sudo cp deploy/systemd/stadtplaner-social-publisher.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now stadtplaner-social-publisher.timer
systemctl list-timers stadtplaner-social-publisher.timer
```

Retryfähige Willkommensmails verwenden eine separate E-Mail-Outbox. Der zugehörige
One-shot-Worker wird ebenfalls minütlich gestartet:

```bash
sudo cp deploy/systemd/stadtplaner-email-outbox.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now stadtplaner-email-outbox.timer
```

Die `.service`-Unit ist bewusst nicht direkt aktivierbar; der Timer startet sie minütlich. Manuell kann ein sicher begrenzter Lauf mit `python -m app.cli.publish_social_outbox --limit 20` ausgeführt werden. Temporäre Netzwerk-, Screenshot-, HTTP-429- und 5xx-Fehler werden mit Backoff erneut versucht; `Retry-After` wird berücksichtigt. Jeder Outbox-Eintrag besitzt einen stabilen Idempotency-Key und erfolgreiche Posts werden samt Remote-, Media-ID und URL persistiert.

Fachliche Einstellungen liegen in `social_publishing_settings` und werden ausschließlich durch Superuser unter `/admin/social` geändert: Master-Switch, automatische oder manuelle Freigabe, Dry Run, Eventthemen, Debounce, Hashtags, Sichtbarkeit und eines der begrenzten Screenshotformate. Für künftig bewusst aus OpenStreetMap übernommene Flächen gibt es den standardmäßig ausgeschalteten Registry-Eintrag `POLYGON_ADOPTED_FROM_OSM` in `enabled_events` und das validierte Linkziel `DETAIL_PAGE` (Default) oder `GIS`. Änderungen werden automatisch als partielle PATCH-Anfragen gespeichert; ein dezenter Status zeigt laufende, erfolgreiche oder fehlgeschlagene Speicherung an. Das Aktivieren erzeugt keinen historischen Backfill. Secrets und Instanz-URL bleiben im Environment. `OFF` pausiert die Queue, ohne Historie oder wartende Ereignisse zu löschen.

Publication Policy:

- Die Feld-Allowlist umfasst ausschließlich öffentlich sichtbare Gebietsattribute. Texte stammen aus kontrollierten Vorlagen und übernehmen keine vollständigen Beschreibungen, Mentions oder fremden Hashtags.
- Änderungen desselben Gebiets werden standardmäßig 300 Sekunden gesammelt.
- Der reguläre OSM-Sync erzeugt keine Social-Events. Ein bewusst ausgeführter `python -m app.cli.sync_analysis_areas --publish-relevant-updates`-Lauf darf neue Gebiete, Namensänderungen und Grenzänderungen oberhalb des konfigurierten Flächenunterschieds einreihen.
- `POLYGON_ADOPTED_FROM_OSM` entsteht ausschließlich beim erfolgreichen Erzeugen eines eigenen `user_polygons`-Datensatzes samt `polygon_osm_sources`-Referenz. Der Outbox-Eintrag wird atomar mit der Übernahme gespeichert; Titel-, Adress- oder Geometrie-Autosaves erzeugen kein weiteres Adoption-Event. Eine feste Verzögerung von 30 Sekunden lässt die unmittelbar folgende öffentliche Adress- und Slug-Ergänzung abschließen, ist aber kein Update-Debounce. Wird die Fläche vor der Verarbeitung gelöscht, wechselt der Eintrag auf `CANCELLED`.
- Der Payload enthält ausschließlich den geprüften `PublicAdoptedPolygonSnapshot`: Polygon-ID, Slug, Titel, Kategorie, Etage, Größenklasse, öffentliche Adresse, Belegungsstatus sowie OSM-Typ und -ID. Das Template wird bei Verarbeitung noch einmal aus dem aktuellen öffentlichen Polygonzustand erstellt.
- Der Statistikimport erzeugt bei tatsächlichen Änderungen höchstens ein Sammelereignis für die Gebietsübersicht, niemals eines pro Beobachtung.
- Technische Zeitstempel-, Cache-, Index-, Login-, Audit- und Rollenänderungen werden nicht veröffentlicht. Löschungen werden ebenfalls nicht automatisch veröffentlicht.
- Eigentümerinformationen, interne Mieten, interne Notizen, Benutzerinformationen und andere nicht öffentliche Daten sind nicht zugelassen.

Jede automatische Veröffentlichung enthält einen Screenshot einer serverseitig bestimmten öffentlichen Route und einen deterministischen Alt-Text. Der Worker lädt die Seite ohne Login, wartet auf `data-social-preview-ready="true"`, erlaubt ausschließlich `/`, `/gebiete...` und `/flaechen...` auf dem konfigurierten Stadtplaner-Origin und lädt das JPEG über Mastodons Media API hoch. Polygonziele sind `/flaechen/{slug}?social-preview=1...` oder `/?polygon={uuid}&social-preview=1...`; der GIS-Ready-State setzt eine geladene Karte und die ausgewählte Fläche voraus. Adminseiten und URLs aus Event-Payloads werden nie geöffnet. Bei einem Screenshotfehler wird kein Text-only-Post gesendet.

Die Datenbank begrenzt `POLYGON_ADOPTED_FROM_OSM` zusätzlich mit einem eindeutigen Index auf `event_type + resource_id`. Der Publisher prüft seine persistierte Publication-History und sendet beim Mastodon-Request einen stabilen Hash der Outbox-ID als `Idempotency-Key`. Mastodon speichert diesen Schlüssel laut aktueller API-Dokumentation zeitlich begrenzt; die lokale Eindeutigkeit bleibt daher die dauerhafte Schutzschicht.

Superuser sehen unter `/admin/social` Verbindung, persistente Einstellungen, Themen, Screenshotdarstellung, Warteschlange, Vorschau und Publication History. Ereignisse im Modus `MANUAL` bleiben nach der Hintergrund-Screenshot-Erzeugung in `PENDING_APPROVAL`, bis sie veröffentlicht oder über ein konsistentes Modal verworfen werden. Access Tokens und Authorization-Header sind dort grundsätzlich nicht Bestandteil der API-Antwort.

## Persönliche Benachrichtigungen

Angemeldete Personen erhalten persistente, empfängerbezogene Hinweise über die Glocke im Kopfbereich. Fachliche Ereignisse aus GIS, Gebietsstatistik, Social Publishing, Importen sowie Konto- und Rollenverwaltung werden durch eine zentrale Policy in kontrollierte Texte, Prioritäten und ausschließlich interne Aktionsziele übersetzt. Abonnements ermöglichen das explizite Folgen von Flächen und Gebieten; Themenpräferenzen liegen kontoweit im Profil. Sicherheitsrelevante Kontohinweise bleiben unabhängig von allgemeinen Präferenzen aktiv.

Gleichartige Änderungen derselben Ressource werden pro Empfänger innerhalb von fünf Minuten zusammengeführt. Gewöhnliche eigene Autosaves erzeugen keine Benachrichtigung. PostgreSQL ist die persistente Zustellquelle; Server-Sent-Events liefern neue Einträge in Echtzeit, während Fokus- und Reconnect-Abgleiche verlorene Verbindungen auffangen. Das fachliche Notification Center ist getrennt vom Auditlog und vom öffentlichen Social-Publishing-Outbox-System.

API-Vertrag, Ereignistaxonomie, Integrationsregeln und Erweiterungsschritte stehen in [docs/notifications.md](docs/notifications.md). Nach dem Alembic-Upgrade sind keine zusätzlichen Secrets erforderlich.

Die reguläre Aufbewahrung beträgt konfigurierbar `NOTIFICATION_RETENTION_DAYS=90`. Alte Einträge werden außerhalb von Requests mit `python -m app.cli.cleanup_notifications` bereinigt; ungelesene handlungsrelevante Hinweise bleiben bis zur Erledigung oder einem expliziten Ablaufdatum bestehen.

## Datenbank

Benötigt wird PostgreSQL mit PostGIS. Beispiel:

```bash
createdb open_city_map
psql open_city_map -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

`backend/.env`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/open_city_map
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
JWT_SECRET_KEY=development-only-change-me-32-bytes-minimum
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30
AUTH_COOKIE_SECURE=false
AUTH_COOKIE_SAMESITE=lax
EMAIL_BACKEND=console
CONTACT_TO_EMAIL=kontakt@example.org
CONTACT_TO_NAME="Stadtplaner / OK Lab Flensburg"
CONTACT_TURNSTILE_ENABLED=false
AVATAR_UPLOAD_DIR=data/uploads
AVATAR_MAX_FILE_SIZE=5242880
AVATAR_OUTPUT_SIZE=512
AVATAR_WEBP_QUALITY=85
MEDIA_BASE_URL=
NOMINATIM_BASE_URL=
NOMINATIM_USER_AGENT="OpenCityMap/0.1"
NOMINATIM_EMAIL=
```

OpenStreetMap-Informationen werden bevorzugt aus der lokalen PostGIS-Tabelle `osm_features` geladen. Einrichtung, Importvertrag, räumliches Ranking und der standardmäßig deaktivierte Overpass-Fallback sind in [docs/osm-data.md](docs/osm-data.md) dokumentiert.

Die vollständige Serveranleitung für den updatefähigen Schleswig-Holstein-Import,
die stündliche OSM-Replikation, Monitoring und Recovery steht in
[docs/osm-hourly-sync.md](docs/osm-hourly-sync.md).

Profilbilder werden lokal unter `AVATAR_UPLOAD_DIR/avatars` gespeichert. Das Verzeichnis wird beim ersten Upload automatisch angelegt. Uploads werden als JPG, PNG oder WebP angenommen, serverseitig mit Pillow dekodiert, auf 512 x 512 Pixel normalisiert und als WebP ohne EXIF-Metadaten gespeichert.

Das öffentliche Kontaktformular sendet ausschließlich an das FastAPI-Backend. `CONTACT_TO_EMAIL` muss für einen tatsächlichen Versand gesetzt sein; SMTP-Absender und Zugangsdaten bleiben serverseitig. Im Modus `EMAIL_BACKEND=console` werden Betreiber-Mail und Absenderkopie nur in der Backend-Konsole ausgegeben. Der Endpoint schützt den Versand durch signierte Formular-Tokens, Origin-Prüfung, Honeypot, Mindestzeit, IP-/E-Mail-Rate-Limits und eine einfache Spam-Heuristik. Cloudflare Turnstile kann optional mit `CONTACT_TURNSTILE_ENABLED=true`, `TURNSTILE_SITE_KEY` und `TURNSTILE_SECRET_KEY` aktiviert werden.

Der Anwendungscode vertraut `X-Forwarded-For` nicht direkt, sondern verwendet die von ASGI bereitgestellte Client-Adresse. Hinter Nginx dürfen Forwarded Headers deshalb nur für den bekannten Proxy aktiviert werden, beispielsweise mit Uvicorn `--proxy-headers --forwarded-allow-ips=127.0.0.1`. Der vorhandene Rate-Limiter arbeitet pro Backend-Prozess; bei mehreren Workern oder Instanzen sollte er später durch einen gemeinsamen Redis-/Proxy-basierten Limiter ersetzt werden.

## Stadtplaner-Kartenstil und VersaTiles

`frontend/.env` konfiguriert Kartenstil und Startposition. Ohne Style-Variable lädt die Anwendung den lokalen Stil `/map-styles/stadtplaner-light.json`. Eine externe URL kann mit `NUXT_PUBLIC_MAP_STYLE_URL` überschrieben werden; `NUXT_PUBLIC_VERSATILES_STYLE_URL` bleibt als veralteter Kompatibilitätsname erhalten. Schlägt der konfigurierte beziehungsweise lokale Stil fehl, wird technisch auf VersaTiles `neutrino` zurückgefallen.

```env
NUXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
NUXT_PUBLIC_SITE_URL=http://localhost:3000
NUXT_PUBLIC_DEFAULT_OG_IMAGE=
NUXT_PUBLIC_MEDIA_BASE_URL=
NUXT_PUBLIC_AVATAR_MAX_UPLOAD_BYTES=5242880
NUXT_PUBLIC_MAP_STYLE_URL=
NUXT_PUBLIC_MAP_PERFORMANCE_DEBUG=false
NUXT_PUBLIC_MAP_CENTER_LNG=9.435
NUXT_PUBLIC_MAP_CENTER_LAT=54.783
NUXT_PUBLIC_MAP_ZOOM=16.4
NUXT_PUBLIC_CONTACT_MAIL=oklabflensburg@grain.one
NUXT_PUBLIC_CONTACT_PHONE="+49 176 59978074"
NUXT_PUBLIC_ADDRESS_NAME="Open Knowledge Lab Flensburg"
NUXT_PUBLIC_ADDRESS_STREET="Am Nordertor"
NUXT_PUBLIC_ADDRESS_HOUSE_NUMBER="2"
NUXT_PUBLIC_ADDRESS_POSTAL_CODE=24939
NUXT_PUBLIC_ADDRESS_CITY=Flensburg
NUXT_PUBLIC_PRIVACY_CONTACT_PERSON=
NUXT_PUBLIC_WEBSITE_ORIGIN=
```

## SEO

Das Frontend erzeugt Canonical-, Open-Graph-, Twitter- und JSON-LD-Daten serverseitig über ein zentrales SEO-Composable. `NUXT_PUBLIC_SITE_URL` muss im Produktivbetrieb auf die öffentliche Origin gesetzt werden; ohne Wert warnt der Production Build und verwendet nur für die lokale Entwicklung `http://localhost:3000`. Ein vorhandenes Social-Preview-Bild kann mit `NUXT_PUBLIC_DEFAULT_OG_IMAGE=/og/default.webp` konfiguriert werden. Solange kein geeignetes Bild hinterlegt ist, werden keine erfundenen Bildmetadaten ausgegeben.

Öffentliche Polygone besitzen persistente URLs unter `/flaechen/<slug>`. Beim Anlegen wird die Geometrie gespeichert, per `ST_PointOnSurface` ein repräsentativer Punkt bestimmt und – falls `NOMINATIM_BASE_URL` gesetzt ist – serverseitig rückwärts geocodiert. Der erste Slug entsteht aus Etage, Straße, Hausnummer und Ort (beispielsweise `eg-holm-42-flensburg`); bei einem Geocoding-Ausfall wird einmalig ein stabiler Fallback wie `eg-flaeche-a83f21` verwendet. Konflikte erhalten `-2`, `-3` usw. Ein einmal vergebener Slug bleibt bei späteren Änderungen stabil.

Gemeinde, Stadtteile und Quartiere verwenden die bereits synchronisierte PostGIS-Struktur `analysis_areas`. Ihre global eindeutigen Slugs werden beim OSM-Sync erzeugt und bei späteren Aktualisierungen bewusst beibehalten. Öffentliche SSR-Seiten unter `/gebiete/<slug>` zeigen ausschließlich räumlich aggregierte Flächen-, Branchen- und POI-Daten, den Vergleich zur Gemeinde sowie Parent-/Child-Beziehungen. Die dynamischen Gebietsrouten werden aus validen Geometrien mit dem gespeicherten `updated_at` in die Sitemap aufgenommen.

Nominatim wird nie direkt aus dem Browser aufgerufen. Der Backend-Service setzt einen konfigurierbaren User-Agent, cached auf fünf Dezimalstellen gerundete Koordinaten und behandelt Timeouts oder Fehler als nicht kritisch: Die Geometrie bleibt gespeichert und die Oberfläche weist getrennt auf die fehlgeschlagene Adressauflösung hin.

Login-, Registrierungs-, Passwort-, Profil- und Sitzungsseiten verwenden `noindex,nofollow`. `/impressum` und `/datenschutz` verwenden `noindex,follow` und sind ausdrücklich von Sitemap, Open Graph, Twitter Cards und JSON-LD ausgeschlossen.

## Layout und statische Seiten

Das Frontend nutzt ein globales Nuxt-Layout mit fixiertem Header, lokal ausgeliefertem OK-Lab-Flensburg-Logo, GIS-Hauptbereich und nicht fixiertem Footer.

Neue Routen:

- `/` interaktive Karte
- `/gebiete` – hierarchisches Verzeichnis von Gemeinde, Stadtteilen und Quartieren
- `/gebiete/<slug>` – öffentliche, serverseitig gerenderte Gebiets- und Standortanalyse
- `/login`
- `/registrieren`
- `/passwort-vergessen`
- `/passwort-zuruecksetzen`
- `/email-bestaetigen`
- `/profil`
- `/profil/sicherheit`
- `/meine-flaechen`
- `/flaechen/neu` – auth-geschützter Zeichen- und Erstellungsflow für neue Flächen
- `/ueber-das-projekt`
- `/open-data`
- `/kontakt`
- `/impressum`
- `/datenschutz`
- `/dokumentation` – öffentliches Benutzerhandbuch mit Suche und responsiver Navigation
- `/dokumentation/<thema>` – thematische Anleitungen, unter anderem Karte, Flächen, Konto und Verwaltung
- `/dokumentation/gebiete`, `/dokumentation/methodik` und `/dokumentation/api`

## Frontend-Dokumentation pflegen

Die integrierte Dokumentation verwendet bewusst kein separates CMS. Inhalte, Reihenfolge, Suchbegriffe, Rollenkennzeichnung und Seitenstruktur liegen typisiert in `frontend/app/config/documentation.ts`. Aus dieser einen Quelle entstehen Seitenleiste, Suche, Inhaltsverzeichnisse, Vor-/Zurück-Navigation und Sitemap-Einträge.

Beim Ergänzen oder Ändern einer Seite:

1. Einen eindeutigen `slug` sowie stabile, kleingeschriebene Abschnitts-IDs vergeben. Bestehende IDs möglichst nicht ändern, da sie als Anker verlinkt werden können.
2. `audience` korrekt als `public`, `login` oder `verwaltung` kennzeichnen. Die Dokumentation erklärt Berechtigungen, ersetzt aber niemals die serverseitige Zugriffskontrolle.
3. Nur bereits vorhandene Produktfunktionen beschreiben und interne Daten nicht in öffentliche Beispiele übernehmen.
4. Suchbegriffe und eine prägnante Beschreibung ergänzen. Die Suche indiziert zusätzlich Überschriften und den Text aller Inhaltsblöcke.
5. Bilder bei Bedarf unter `frontend/public/docs/` ablegen und nur aktuelle, anonymisierte Screenshots verwenden. Die Inhaltsarchitektur funktioniert vollständig ohne Bilder.
6. `cd frontend && pnpm test && pnpm typecheck && pnpm build` ausführen.

Die Darstellung erfolgt über wiederverwendbare Komponenten in `frontend/app/components/docs/`. Öffentliche Dokumentationsseiten sind indexierbar, besitzen Canonical-, Open-Graph- und JSON-LD-Metadaten und werden automatisch in die XML-Sitemap aufgenommen.

## Dialoge & Bestätigungen

Allgemeine Frontend-Dialoge verwenden ausschließlich `frontend/app/components/ui/AppModal.vue`. Die Komponente stellt Overlay, Größen (`sm`, `md`, `lg`, `xl`), Header, einen intern scrollbaren Inhaltsbereich, optionalen Footer, Fokusfalle, Fokus-Rückgabe, Escape-/Overlay-Verhalten und den verschachtelungssicheren Body-Scroll-Lock bereit. Formdialoge liefern nur ihren fachlichen Inhalt; sie bauen keine eigene Teleport-, Overlay- oder Fokus-Shell.

Kurze Entscheidungen verwenden `frontend/app/components/ui/AppConfirmDialog.vue` auf Basis von `AppModal`. Die Varianten `default`, `warning` und `danger`, die Reihenfolge „Abbrechen, Bestätigen“, Loading-Sperre und Inline-API-Fehler sind damit zentral festgelegt. Der destruktive Button erhält beim Öffnen bewusst nicht den initialen Fokus. Die konkrete Seite oder Fachkomponente hält den lokalen Zustand und führt den Request aus, damit ein fehlgeschlagener Request den Dialog offen lassen kann. Ein globaler `useConfirmDialog()`-Host wird deshalb derzeit nicht verwendet; sollte später ein globaler Host ergänzt werden, muss dessen API auch asynchrone Loading- und Fehlerzustände innerhalb desselben Dialogs abbilden.

Die Auswahl des Feedback-Musters folgt diesen Regeln:

- Modal: Bestätigung, kurze Form oder kritische Aktion.
- Toast beziehungsweise bestehender Inline-Status: nicht blockierendes Erfolgsfeedback.
- Inline-Fehler: Formularvalidierung und lokal behandelbare Request-Fehler.
- `AppBottomSheet`: lange mobile GIS-Panels wie Filter und Analyse; kein Ersatz für kurze Bestätigungen.

Native `alert()`, `confirm()` und `prompt()` sind im produktiven Frontend nicht zulässig.

## Authentifizierung und Schreibrechte

Konten können unter `/profil/sicherheit` TOTP-Zwei-Faktor-Authentifizierung einrichten. Passwort- und OAuth-Login werden für aktivierte Konten vor Ausgabe der bestehenden Access-/Refresh-Cookies durch dieselbe kurzlebige MFA-Challenge geschützt. QR-Codes entstehen lokal im Browser; Authenticator-Secrets liegen verschlüsselt und Wiederherstellungscodes nur gehasht in PostgreSQL. Die Sicherheitsinvarianten und der Deployment-Ablauf sind in [docs/security/mfa.md](docs/security/mfa.md) beschrieben.

Passkeys/WebAuthn sind als bevorzugte Anmeldung, passwortloser Login und MFA-Step-up integriert. Mehrere Credentials pro Konto werden unterstützt; der Server speichert nur Public Keys und technische Credential-Metadaten. Details zu Challenge-Replay-Schutz, Sign Counter, RP-Konfiguration und HTTPS stehen in [docs/security/passkeys.md](docs/security/passkeys.md).

Für den Betrieb muss ein eigener Fernet-Schlüssel gesetzt und die Migration ausgeführt werden:

```env
MFA_ENCRYPTION_KEY=<mit Fernet.generate_key() erzeugter Wert>
MFA_CHALLENGE_EXPIRE_SECONDS=300
MFA_MAX_ATTEMPTS=5
MFA_TOTP_ISSUER="Stadtplaner - OK Lab Flensburg"
MFA_TOTP_VALID_WINDOW=1
MFA_RECOVERY_CODE_COUNT=10
REAUTH_MAX_AGE_SECONDS=600
REQUIRE_MFA_FOR_SUPERUSERS=false
WEBAUTHN_RP_ID=localhost
WEBAUTHN_RP_NAME="Stadtplaner OK Lab Flensburg"
WEBAUTHN_ORIGIN=http://localhost:3000
WEBAUTHN_CHALLENGE_EXPIRE_SECONDS=300
WEBAUTHN_TIMEOUT_MS=60000
```

```bash
cd backend
alembic upgrade head
```

Lesender Zugriff auf Karte, Polygone und Analysen bleibt öffentlich. Schreibende Operationen sind serverseitig geschützt:

- `POST /api/v1/polygons`
- `PUT /api/v1/polygons/{id}`
- `PATCH /api/v1/polygons/{id}`
- `DELETE /api/v1/polygons/{id}`

Die Anmeldung erfolgt über HttpOnly-Cookies für Access- und Refresh-Tokens. Der Refresh Token wird serverseitig nur gehasht in `user_sessions` gespeichert und bei jedem Refresh atomar rotiert. Datensätze derselben Anmeldesitzung teilen eine `family_id`; `SELECT … FOR UPDATE` verhindert einen doppelten Verbrauch. Ein erneut verwendeter rotierter Token widerruft nach einem kurzen, konfigurierbaren Multi-Tab-Toleranzfenster die aktive Tokenfamilie und erzeugt `REFRESH_TOKEN_REUSE_DETECTED`. Logout widerruft ebenfalls die gesamte Familie. Mutierende Requests verwenden zusätzlich ein CSRF-Token im Double-Submit-Verfahren; der Refresh-Endpunkt prüft wegen möglicher Hard Reloads stattdessen die erlaubte Browser-Origin.

Alle regulären Frontend-Anfragen laufen über `frontend/app/composables/useApi.ts`. Antwortet ein geschützter Endpoint mit `ACCESS_TOKEN_EXPIRED` oder `AUTH_REQUIRED`, führt der Client transparent genau einen `POST /api/v1/auth/refresh` aus und wiederholt die ursprüngliche Anfrage einmal. Ein Single-Flight-Koordinator sorgt dafür, dass parallele 401-Antworten im selben Tab denselben Refresh abwarten. Login, Registrierung, Refresh, Logout, Passwort-Reset und OAuth-Flows sind von diesem Retry ausgeschlossen; 403-Antworten lösen grundsätzlich keinen Refresh aus. Eindeutige Refresh-401 leeren die Sitzung, Netzwerkfehler, 409-Rotationskonflikte und 5xx-Fehler dagegen nicht.

Die clientseitige Auth-Initialisierung lädt `GET /api/v1/auth/session`, das den aktuellen Benutzer einschließlich Rollen sowie das zugehörige CSRF-Token liefert. Ist nur das Access-Cookie abgelaufen, greift derselbe zentrale Refresh-Retry, bevor Middleware über einen Login-Redirect entscheidet. Ein echter Sitzungsablauf führt zu `/login?redirect=<interner-pfad>&session_expired=1`. Der Generation Counter im Auth Store verhindert, dass ein bereits laufender Refresh einen später gestarteten Logout lokal rückgängig macht. SSR verwendet bewusst kein prozessweites Refresh-Promise und teilt daher niemals Auth-Zustand verschiedener Requests.

Neue Nutzerkonten starten mit `is_verified=false`. Login ist möglich. Das Anlegen einer Fläche und das Löschen einer eigenen Fläche erfordern ein aktives angemeldetes Konto; Änderungen an öffentlichen Polygonfeldern setzen zusätzlich die E-Mail-Verifikation voraus. Standard-Ownership-Regel:

- Superuser dürfen Polygone erstellen sowie alle Polygone bearbeiten und löschen.
- Konten mit der exakten Rolle `VERWALTUNG` dürfen alle öffentlichen Polygonfelder sowie die getrennten Verwaltungsdaten bearbeiten.
- Normale Nutzer dürfen nur Polygone bearbeiten oder löschen, deren technischer Ersteller `created_by_user_id` ihrer User-ID entspricht.
- Jeder aktive angemeldete Nutzer darf über `/flaechen/neu` ein Polygon erstellen; der Server setzt dabei `created_by_user_id` und `updated_by_user_id` selbst.
- Neue Polygone erhalten `created_by_user_id` ausschließlich serverseitig.

Create und Delete sind getrennte zentrale Berechtigungsentscheidungen. Fachliche Eigentümerfelder (`owner_*`) beeinflussen diese Rechte nicht. Die Übersichtskarte `/` bleibt schreibgeschützt; Geometrien werden zum Erstellen ausschließlich auf `/flaechen/neu` und zum späteren Bearbeiten ausschließlich auf der Detailseite gezeichnet.

Die Kategorien inklusive Labels und Farben werden zentral in `frontend/app/utils/industries.ts` gepflegt. Karte, Detailkarte, Kategorie-Badge, Branchenfilter und Analytics-Chart leiten ihre Farben aus dieser Quelle ab. Unbekannte historische Kategorien behalten ihren Text und erhalten eine neutrale Fallback-Farbe.

Rollen liegen als Liste im User-Datensatz und werden zentral serverseitig geprüft. Der öffentliche SSR-Endpunkt `/api/v1/polygons/by-slug/{slug}` liefert niemals Eigentümerdaten oder Preise. `GET/PATCH /api/v1/polygons/{id}/verwaltung` ist ausschließlich für `VERWALTUNG` (und bestehende Superuser) erreichbar und antwortet mit `Cache-Control: private, no-store`. Der fachliche Eigentümer (`owner_*`) ist ausdrücklich nicht der System-Ersteller (`created_by_user_id`). Geldwerte werden als PostgreSQL `NUMERIC(12,2)` beziehungsweise Python `Decimal` gespeichert.

Die Detailseite speichert Text nach 700 ms Ruhezeit, Etage und abgeschlossene Geometrieänderungen sofort. Eine gemeinsame Queue sendet nie parallele PATCH-Requests, übernimmt jeweils die jüngste Serverversion und meldet Versionskonflikte per HTTP 409. Private Verwaltungsdaten werden erst clientseitig nach der Authentifizierung geladen und gelangen daher weder in öffentliches SSR-HTML noch in Open Graph, JSON-LD oder die Sitemap.

## Stadtweite Kennzahlen

Leerstand, Filialisierung, Zentralitätsindex und Kaufkraftindex werden zentral in der PostgreSQL-Tabelle `city_metrics` gespeichert. Die Werte sind nullable; es gibt keine Beispielwerte oder fachlichen Defaults. Leerstand und Filialisierung werden als Prozentpunkte in `NUMERIC(5,2)` gespeichert (`6.25` bedeutet `6,25 %`). Zentralität und Kaufkraft verwenden `NUMERIC(8,2)` und dürfen wie die Prozentwerte nicht negativ sein. Für Prozentwerte gilt zusätzlich der Wertebereich 0 bis 100.

Die Datensätze enthalten außerdem den fachlichen Datenstand (`reference_date`), eine optionale Quelle, interne Hinweise, Änderungszeitpunkte und die serverseitig gesetzte `updated_by_user_id`. Aktuell werden alle vier Kennzahlen manuell durch `VERWALTUNG` gepflegt; die Anwendung berechnet sie nicht aus unzureichenden Polygonattributen. Quelle und Hinweise werden ausschließlich über den geschützten Verwaltungsendpunkt ausgeliefert.

API-Endpunkte:

- `GET /api/v1/analytics/fast-facts` – öffentliche stadtweite Kennzahlen
- `GET /api/v1/analytics/fast-facts/verwaltung` – Kennzahlen inklusive Quelle und Hinweisen, nur `VERWALTUNG`
- `PATCH /api/v1/analytics/fast-facts` – partielles Aktualisieren oder Leeren einzelner Werte, nur `VERWALTUNG`
- `GET /api/v1/analytics/overview` – Kennzahlen zusammen mit berechneter Shopanzahl und Branchenverteilung

Die Kennzahlen-Card auf der Karte ist ausschließlich lesend und zeigt fehlende Werte als `—`. Die Bearbeitung erfolgt auf der eigenen, nicht indexierbaren Seite `/verwaltung/kennzahlen`. Der zugehörige Menüeintrag und die Route sind nur für `VERWALTUNG` und bestehende Superuser verfügbar; normale und ausgeloggte Nutzer haben ausschließlich Lesezugriff. Änderungen werden erst mit „Speichern“ übertragen und anschließend unmittelbar im Analytics-Store aktualisiert. Der Backend-Endpunkt erzwingt die Rolle unabhängig von der Frontend-Navigation zusätzlich serverseitig.

## Administratives Auditlog

Das bestehende `admin_audit_logs`-Modell wird über den paginierten read-only Endpoint `GET /api/v1/admin/audit-logs` und die nicht indexierbare Nuxt-Seite `/admin/audit-log` sichtbar gemacht. Beide Zugriffsebenen sind ausschließlich für `is_superuser = true` vorgesehen; `VERWALTUNG` allein reicht nicht aus. Filterung und Pagination erfolgen in PostgreSQL, die Standardabfrage nutzt den vorhandenen `created_at`-Index, und potenziell sensible Metadaten werden vor der DTO-Ausgabe rekursiv redigiert. Es gibt weder einen Auditlog-Schreib-/Löschendpoint noch eine entsprechende UI-Aktion.

## Kommunale Statistik

Der Zahlenspiegel der Stadt Flensburg wird wöchentlich über die öffentliche Superset-Chart-Data-API geprüft und normalisiert in PostgreSQL importiert. Die Zeitreihen von 2011 bis 2025 werden über eine explizite Zuordnung der amtlichen Stadtteilnummern 01–13 mit `analysis_areas` verknüpft. Quartiere erhalten keine erfundenen Werte, sondern klar gekennzeichnete Parent-Stadtteilwerte. Rohdateien liegen nicht im Repository; Quelle, Datenstand und Datenlizenz Deutschland – Zero – Version 2.0 werden auf den Gebietsseiten angezeigt. Die technische Discovery und Methodik stehen in [docs/flensburg-statistics.md](docs/flensburg-statistics.md).

Externe OAuth-/OIDC-Konten werden über `user_oauth_accounts` mit lokalen Benutzern verknüpft. Die Tabelle speichert nur Provider, stabile Provider-Subject-ID, optionale Metadaten und Zeitpunkte, aber keine Provider Access Tokens. Zentralisierte Identitäten sind über `(provider, provider_subject)` eindeutig; föderierte Mastodon-Identitäten über `(provider, provider_instance, provider_subject)`. Pro lokalem Konto bleibt `(user_id, provider)` eindeutig.

Das Frontend lädt aktivierte Anbieter öffentlich über `GET /api/v1/auth/oauth/providers` und startet OAuth per Browsernavigation zu `/api/v1/auth/oauth/{provider}/login`. In der lokalen Entwicklung müssen beim Provider die Backend-Callback-URLs hinterlegt werden:

- GitHub: `http://localhost:8000/api/v1/auth/oauth/github/callback`
- Google: `http://localhost:8000/api/v1/auth/oauth/google/callback`
- Mastodon: `http://localhost:8000/api/v1/auth/oauth/mastodon/callback`

OAuth-Secrets bleiben ausschließlich im Backend (`GITHUB_CLIENT_SECRET`, `GOOGLE_CLIENT_SECRET`). Das Frontend benötigt nur `NUXT_PUBLIC_API_BASE_URL`.

Ein Provider wird nur aktiviert und im Frontend angezeigt, wenn in `backend/.env` sowohl seine Client-ID als auch sein Client-Secret gesetzt sind:

```env
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# Separater föderierter Login; verwendet niemals MASTODON_ACCESS_TOKEN.
MASTODON_SSO_ENABLED=false
MASTODON_SSO_CLIENT_NAME=Stadtplaner
MASTODON_SSO_DEFAULT_INSTANCE=https://norden.social
MASTODON_SSO_ENCRYPTION_KEY=
```

Den separaten Schlüssel für die Verschlüsselung dynamisch registrierter Mastodon-App-Credentials erzeugen:

```bash
cd backend
.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Der Schlüssel muss nach der ersten produktiven Verwendung dauerhaft und gesichert aufbewahrt werden. Ein unvorbereiteter Austausch macht bereits gespeicherte Instanz-Credentials unlesbar; für eine geplante Rotation müssen diese kontrolliert neu verschlüsselt oder die betroffenen App-Registrierungen neu aufgebaut werden.

Mastodon SSO ist föderiert: Der Nutzer gibt zunächst seine Instanz an. Das Backend normalisiert den Host, verwirft lokale/private/reservierte Ziele einschließlich DNS- und Redirect-Zielen, prüft die öffentliche Mastodon-Instance-API und registriert über `POST /api/v1/apps` einmalig eine vertrauliche OAuth-Anwendung pro Instanz. Client-ID und Client-Secret werden mit dem separaten ENV-Master-Key verschlüsselt in `mastodon_oauth_instances` gespeichert und wiederverwendet. Fehlgeschlagene Registrierungen erhalten ein kurzes Backoff.

Der Autorisierungsfluss verwendet Authorization Code, einen opaken kurzlebigen und einmal verwendbaren DB-State sowie PKCE S256. Moderne Instanzen erhalten ausschließlich den Scope `profile`; bei älteren Mastodon-Versionen ohne OAuth-Discovery wird `read:accounts` verwendet. Nach `GET /api/v1/accounts/verify_credentials` wird das individuelle User-Access-Token verworfen. Mastodon liefert keine vertrauenswürdige E-Mail-Adresse; neue Konten müssen daher im Profil eine E-Mail hinterlegen und über den bestehenden Stadtplaner-Versand bestätigen.

`MASTODON_ACCESS_TOKEN` ist davon strikt getrennt und wird ausschließlich für automatische Veröffentlichungen des OK-Lab-Accounts verwendet. Mastodon-SSO fordert weder `write:statuses` noch `write:media`, `follow` oder administrative Scopes an.

Für die GitHub OAuth App ist die Authorization callback URL
`<öffentliche Backend-Origin>/api/v1/auth/oauth/github/callback` einzutragen. In der Google Cloud Console lautet die Authorized redirect URI entsprechend
`<öffentliche Backend-Origin>/api/v1/auth/oauth/google/callback`. Falls die öffentliche Backend-Origin von `API_BASE_URL` abweicht, wird sie mit `OAUTH_REDIRECT_BASE_URL` konfiguriert. Nach einer Änderung der OAuth-Variablen muss das Backend neu gestartet werden.

## Rechtliche Betreiberangaben

Die offiziellen Kontaktdaten wurden aus dem Referenzprojekt `oklabflensburg/open-school-map` und der OK-Lab-Flensburg-Projektfamilie übernommen:

- Open Knowledge Lab Flensburg
- Am Nordertor 2, 24939 Flensburg
- `oklabflensburg@grain.one`
- `+49 176 59978074`

Diese Werte werden zentral über Nuxt Runtime Config bereitgestellt und können in der Produktion über `NUXT_PUBLIC_*` Variablen überschrieben werden. Eine konkrete verantwortliche Person wird nicht automatisch aus anderen Projekten übernommen.

Vor einem öffentlichen Produktivbetrieb müssen mindestens geprüft und ergänzt werden:

- Verantwortlichkeit nach § 18 Abs. 2 MStV
- gegebenenfalls vertretungsberechtigte Person, Rechtsform und weitere DDG-Pflichtangaben
- Hosting-Anbieter, Server-Log-Konfiguration und Aufbewahrungsfristen
- konkrete produktive Karten-/Tile-Quelle
- Rechtsgrundlagen, Löschfristen und Betroffenenrechte

Aktuell erkannte technische Datenflüsse:

- MapLibre GL rendert die Karte im Browser.
- Standard ist der lokal ausgelieferte MapLibre-Stil `stadtplaner-light`; `NUXT_PUBLIC_MAP_STYLE_URL` kann ihn installationsabhängig überschreiben.
- Der eigene Stil verwendet 24 Basemap-Layer und zeichnet keine Handels- oder Gastro-POIs zusätzlich zu den interaktiven Stadtplaner-Layern. VersaTiles `neutrino` dient nur als technischer Fallback.
- `NUXT_PUBLIC_MAP_PERFORMANCE_DEBUG=true` aktiviert im Production-Build den lokalen Diagnose-Hook `window.__stadtplanerMapPerformance`. Im Development-Modus ist er automatisch verfügbar; er sendet keine Messdaten und schreibt nicht in die Konsole.
- Der reproduzierbare Chromium-Lauf ist unter `frontend/scripts/profile-map.mjs` dokumentiert. Details und Messwerte stehen in `docs/map-performance.md`.
- Polygon-, Analyse- und Auth-Funktionen kommunizieren mit dem FastAPI-Backend unter `NUXT_PUBLIC_API_BASE_URL`.
- Benutzerkonten, gehashte Passwörter, gehashte Auth-/Verifikations-/Reset-Tokens, Sitzungen sowie Geometrien und Polygon-Eigenschaften werden in PostgreSQL/PostGIS gespeichert.
- Optionale Profilbilder werden als normalisierte WebP-Dateien im lokalen Upload-Verzeichnis gespeichert; in der Datenbank liegt nur die Avatar-URL.
- Der lokale Standardstil lädt Vector Tiles und Glyphs von `tiles.versatiles.org`; Sprites werden nicht benötigt.
- Das Frontend speichert keine JWTs in `localStorage` oder `sessionStorage`; Auth läuft über Cookies.
- Im Frontend-Code wurden keine externen Webfonts, keine Nutzungsanalyse-Integration und keine externen Video-Einbettungen gefunden.

## Production Environment

Für Produktivbetrieb müssen mindestens gesetzt und geprüft werden:

- `APP_ENVIRONMENT=production`
- `JWT_SECRET_KEY` mit starkem geheimem Wert
- `AUTH_COOKIE_SECURE=true`
- `CORS_ORIGINS` ohne Wildcard und mit produktiver Frontend-Origin
- `APP_BASE_URL` und `API_BASE_URL`
- Avatar-Storage über `AVATAR_UPLOAD_DIR`, `AVATAR_MAX_FILE_SIZE`, `AVATAR_OUTPUT_SIZE`, `AVATAR_WEBP_QUALITY` und optional `MEDIA_BASE_URL`
- SMTP-Variablen oder bewusstes E-Mail-Backend sowie `CONTACT_TO_EMAIL`
- optionale OAuth-Provider-Secrets nur für tatsächlich eingesetzte Provider
- Hosting-/Log-Aufbewahrung, Datenschutztexte und Betreiberangaben

## Tests

```bash
cd frontend && pnpm test
cd backend && pytest
```
