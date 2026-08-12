# Open City Map

Produktionsnaher GIS-Monorepo-Scaffold mit Nuxt 4, TailwindCSS 4, MapLibre, Terra Draw, FastAPI, Cookie-basierter Authentifizierung und PostgreSQL/PostGIS.

## Struktur

- `frontend/` Nuxt 4 GIS-UI mit Filter-Drawer, MapLibre-Karte, Terra-Draw-Polygoneditor und Analysepanel
- `backend/` FastAPI REST API mit SQLAlchemy 2, GeoAlchemy2, Alembic, PostGIS, Argon2id-Passwort-Hashing und JWT/Refresh-Session-Verwaltung

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
AVATAR_UPLOAD_DIR=data/uploads
AVATAR_MAX_FILE_SIZE=5242880
AVATAR_OUTPUT_SIZE=512
AVATAR_WEBP_QUALITY=85
MEDIA_BASE_URL=
NOMINATIM_BASE_URL=
NOMINATIM_USER_AGENT="OpenCityMap/0.1"
NOMINATIM_EMAIL=
```

Profilbilder werden lokal unter `AVATAR_UPLOAD_DIR/avatars` gespeichert. Das Verzeichnis wird beim ersten Upload automatisch angelegt. Uploads werden als JPG, PNG oder WebP angenommen, serverseitig mit Pillow dekodiert, auf 512 x 512 Pixel normalisiert und als WebP ohne EXIF-Metadaten gespeichert.

## VersaTiles

`frontend/.env` konfiguriert Kartenquelle und Startposition:

```env
NUXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
NUXT_PUBLIC_SITE_URL=http://localhost:3000
NUXT_PUBLIC_DEFAULT_OG_IMAGE=
NUXT_PUBLIC_MEDIA_BASE_URL=
NUXT_PUBLIC_AVATAR_MAX_UPLOAD_BYTES=5242880
NUXT_PUBLIC_VERSATILES_STYLE_URL=https://tiles.versatiles.org/assets/styles/colorful/style.json
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

Nominatim wird nie direkt aus dem Browser aufgerufen. Der Backend-Service setzt einen konfigurierbaren User-Agent, cached auf fünf Dezimalstellen gerundete Koordinaten und behandelt Timeouts oder Fehler als nicht kritisch: Die Geometrie bleibt gespeichert und die Oberfläche weist getrennt auf die fehlgeschlagene Adressauflösung hin.

Login-, Registrierungs-, Passwort-, Profil- und Sitzungsseiten verwenden `noindex,nofollow`. `/impressum` und `/datenschutz` verwenden `noindex,follow` und sind ausdrücklich von Sitemap, Open Graph, Twitter Cards und JSON-LD ausgeschlossen.

## Layout und statische Seiten

Das Frontend nutzt ein globales Nuxt-Layout mit fixiertem Header, lokal ausgeliefertem OK-Lab-Flensburg-Logo, GIS-Hauptbereich und nicht fixiertem Footer.

Neue Routen:

- `/` interaktive Karte
- `/login`
- `/registrieren`
- `/passwort-vergessen`
- `/passwort-zuruecksetzen`
- `/email-bestaetigen`
- `/profil`
- `/profil/sicherheit`
- `/meine-flaechen`
- `/ueber-das-projekt`
- `/open-data`
- `/kontakt`
- `/impressum`
- `/datenschutz`

## Authentifizierung und Schreibrechte

Lesender Zugriff auf Karte, Polygone und Analysen bleibt öffentlich. Schreibende Operationen sind serverseitig geschützt:

- `POST /api/v1/polygons`
- `PUT /api/v1/polygons/{id}`
- `PATCH /api/v1/polygons/{id}`
- `DELETE /api/v1/polygons/{id}`

Die Anmeldung erfolgt über HttpOnly-Cookies für Access- und Refresh-Tokens. Der Refresh Token wird serverseitig nur gehasht in `user_sessions` gespeichert und bei jedem Refresh rotiert. Mutierende Requests verwenden zusätzlich ein CSRF-Token im Double-Submit-Verfahren.

Neue Nutzerkonten starten mit `is_verified=false`. Login ist möglich, Polygon-Schreibrechte werden aber erst nach E-Mail-Verifikation erteilt. Standard-Ownership-Regel:

- Superuser dürfen alle Polygone bearbeiten.
- Konten mit der exakten Rolle `VERWALTUNG` dürfen alle öffentlichen Polygonfelder sowie die getrennten Verwaltungsdaten bearbeiten.
- Normale Nutzer dürfen nur Polygone bearbeiten oder löschen, deren `created_by_user_id` ihrer User-ID entspricht.
- Neue Polygone erhalten `created_by_user_id` ausschließlich serverseitig.

Rollen liegen als Liste im User-Datensatz und werden zentral serverseitig geprüft. Der öffentliche SSR-Endpunkt `/api/v1/polygons/by-slug/{slug}` liefert niemals Eigentümerdaten oder Preise. `GET/PATCH /api/v1/polygons/{id}/verwaltung` ist ausschließlich für `VERWALTUNG` (und bestehende Superuser) erreichbar und antwortet mit `Cache-Control: private, no-store`. Der fachliche Eigentümer (`owner_*`) ist ausdrücklich nicht der System-Ersteller (`created_by_user_id`). Geldwerte werden als PostgreSQL `NUMERIC(12,2)` beziehungsweise Python `Decimal` gespeichert.

Die Detailseite speichert Text nach 700 ms Ruhezeit, Etage und abgeschlossene Geometrieänderungen sofort. Eine gemeinsame Queue sendet nie parallele PATCH-Requests, übernimmt jeweils die jüngste Serverversion und meldet Versionskonflikte per HTTP 409. Private Verwaltungsdaten werden erst clientseitig nach der Authentifizierung geladen und gelangen daher weder in öffentliches SSR-HTML noch in Open Graph, JSON-LD oder die Sitemap.

Externe OAuth-/OIDC-Konten werden über `user_oauth_accounts` mit lokalen Benutzern verknüpft. Die Tabelle speichert nur Provider, stabile Provider-Subject-ID, optionale Metadaten und Zeitpunkte, aber keine Provider Access Tokens. Eindeutig sind sowohl `(provider, provider_subject)` als auch `(user_id, provider)`.

Das Frontend lädt aktivierte Anbieter öffentlich über `GET /api/v1/auth/oauth/providers` und startet OAuth per Browsernavigation zu `/api/v1/auth/oauth/{provider}/login`. In der lokalen Entwicklung müssen beim Provider die Backend-Callback-URLs hinterlegt werden:

- GitHub: `http://localhost:8000/api/v1/auth/oauth/github/callback`
- Google: `http://localhost:8000/api/v1/auth/oauth/google/callback`

OAuth-Secrets bleiben ausschließlich im Backend (`GITHUB_CLIENT_SECRET`, `GOOGLE_CLIENT_SECRET`). Das Frontend benötigt nur `NUXT_PUBLIC_API_BASE_URL`.

Ein Provider wird nur aktiviert und im Frontend angezeigt, wenn in `backend/.env` sowohl seine Client-ID als auch sein Client-Secret gesetzt sind:

```env
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

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
- Die Standard-Kartenquelle ist per `NUXT_PUBLIC_VERSATILES_STYLE_URL` konfiguriert und zeigt auf VersaTiles.
- Polygon-, Analyse- und Auth-Funktionen kommunizieren mit dem FastAPI-Backend unter `NUXT_PUBLIC_API_BASE_URL`.
- Benutzerkonten, gehashte Passwörter, gehashte Auth-/Verifikations-/Reset-Tokens, Sitzungen sowie Geometrien und Polygon-Eigenschaften werden in PostgreSQL/PostGIS gespeichert.
- Optionale Profilbilder werden als normalisierte WebP-Dateien im lokalen Upload-Verzeichnis gespeichert; in der Datenbank liegt nur die Avatar-URL.
- Die Standard-Style-Datei von VersaTiles lädt Vector Tiles, Glyphs und Sprites von `tiles.versatiles.org`.
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
- SMTP-Variablen oder bewusstes E-Mail-Backend
- optionale OAuth-Provider-Secrets nur für tatsächlich eingesetzte Provider
- Hosting-/Log-Aufbewahrung, Datenschutztexte und Betreiberangaben

## Tests

```bash
cd frontend && pnpm test
cd backend && pytest
```
