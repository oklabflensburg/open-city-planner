# Externe Anbieter-Icons im Frontend

Das Frontend stellt bekannte externe Anbieter über die zentrale Komponente
`frontend/app/components/external/ProviderIcon.vue` dar. Die Komponente rendert
dekorative, nicht fokussierbare SVGs; der zugängliche Name kommt immer aus dem
benachbarten Link- oder Schaltflächentext. Zur Laufzeit werden keine Icons von
externen Hosts geladen.

## Audit-Matrix

| Anbieter | Gefundene Vorkommen | Vorher | Zentraler Stand |
| --- | --- | --- | --- |
| Google | Login, Registrierung, Profil/Verknüpfungen | ohne Icon | `ProviderIcon` |
| GitHub | Login, Registrierung, Profil, Projektlinks, Footer, Open Data, Dokumentation | teilweise Lucide `Github`, teilweise ohne Anbieterkennung | `ProviderIcon` |
| Mastodon | Login, Registrierung, Instanzdialog, Profil, Footer, Projektseite, Admin Social, Dokumentation | Lucide `MessageCircle` oder ohne Anbieterkennung | `ProviderIcon` |
| OpenStreetMap | Flächendetail, OSM-Objektkarten, OSM-Sidebar, Quellenhinweis und Beitragsdialog | Text oder `ExternalLink` | `ProviderIcon` an expliziten Anbieteraktionen; ruhige GIS-Filter bleiben ohne Markenlogo |
| Wikipedia | externe Quellen auf Gebietsseiten | nur `ExternalLink` | `ProviderIcon` plus `ExternalLink` |
| Wikidata | externe Quellen auf Gebietsseiten | nur `ExternalLink` | `ProviderIcon` plus `ExternalLink` |

StreetComplete und der iD-Editor kommen ebenfalls als externe Werkzeuge vor.
Sie behalten bewusst das allgemeine External-Link-System: iD ist kein eigener
Anmeldeanbieter, und für StreetComplete wird ohne zusätzliches freigegebenes
Asset kein falsches OpenStreetMap-Logo eingesetzt.

## Quellen und Nutzungsbedingungen

- **Google:** Das lokale Asset
  `frontend/public/branding/providers/google.svg` stammt unverändert aus dem
  offiziellen Downloadpaket „Sign in with Google“ für Android/Web, Light,
  Square, Icon-only (Abruf 18. August 2026). Google verlangt das farbige Super-G,
  unveränderte Proportionen und einen klaren Aktionstext neben dem Icon:
  <https://developers.google.com/identity/branding-guidelines>.
- **GitHub:** Die Invertocat-Geometrie folgt Simple Icons 16.21.0; deren Quelle
  ist GitHubs offizielles Brand Toolkit. GitHub erlaubt das Zeichen insbesondere
  für Links, Social Buttons und Integrationshinweise. Es wird nur schwarz oder
  weiß mit ausreichendem Kontrast dargestellt und nicht als Stadtplaner-Logo
  verwendet: <https://brand.github.com/foundations/logo>.
- **Mastodon:** Die Geometrie folgt Simple Icons 16.21.0 und dessen Verweis auf
  Mastodons offizielles `logo-symbol-icon.svg`. Verwendet wird die aktuelle
  Primärfarbe `#6364FF`; Wortmarke und Symbol werden nicht verändert:
  <https://joinmastodon.org/branding>.
- **OpenStreetMap:** Die kompakte Geometrie und Markenfarbe folgen Simple Icons
  16.21.0, dessen Quelle und Richtlinien auf OpenStreetMap/OSMF verweisen. Das
  Zeichen wird nur zur eindeutigen Benennung und Verlinkung des Dienstes benutzt.
  OpenStreetMap und das Lupenlogo sind Marken der OpenStreetMap Foundation:
  <https://wiki.openstreetmap.org/wiki/Logos>.
- **Wikipedia:** Die kompakte W-Geometrie folgt Simple Icons 16.21.0 und dessen
  Wikimedia-Commons-Quelle. Sie bleibt einfarbig und wird ausschließlich neben
  Links zu Wikipedia verwendet. Wikipedia und die zugehörigen Zeichen sind
  Marken der Wikimedia Foundation:
  <https://foundation.wikimedia.org/wiki/Trademark_policy>.
- **Wikidata:** Die drei farbigen Balkengruppen stammen aus dem offiziellen
  `Wikidata-logo.svg` von Wikimedia Commons. Das einfache Zeichen ist dort als
  gemeinfrei gekennzeichnet; Markenrechte und Wikimedia-Richtlinien bleiben
  unberührt: <https://commons.wikimedia.org/wiki/File:Wikidata-logo.svg>.

Die im Code übernommenen Simple-Icons-Vektordaten stehen unter CC0 1.0. Das
hebt Markenrechte der jeweiligen Anbieter nicht auf; maßgeblich bleiben deren
verlinkte Richtlinien und die rein beschreibende Verwendung im Stadtplaner:
<https://github.com/simple-icons/simple-icons/blob/develop/LICENSE.md> und
<https://github.com/simple-icons/simple-icons/blob/develop/DISCLAIMER.md>.
