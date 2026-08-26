# Analysis Areas als erstes Produktionsmodul

Die Migration aus #107 setzt den für #127 geplanten Analysis-Areas-Umbau als
Pilot des modularen Hosts um. Die Abhängigkeitsklassifikation steht im
[Dependency Inventory](analysis-areas-dependency-inventory.md), der ausführbare
Modulvertrag im [Backend-README](../../backend/app/modules/analysis_areas/README.md).

## Kompatibilitätsentscheidungen

- Alle `/api/v1/analysis-areas/**`-Routen bleiben erhalten; es gibt keinen neuen
  `/modules/analysis-areas`-Prefix.
- `/gebiete` und `/gebiete/:slug` kommen aus dem aktivierten Nuxt-Layer. SEO,
  Sitemap-Discovery und Social Preview verwenden dieselben URLs.
- `analysis_areas` bleibt im öffentlichen PostgreSQL-Schema. UUIDs, Slugs,
  Parent-Beziehungen, Geometrien und Zeitstempel werden nicht migriert.
- Fremde Aggregationslogik wird nicht in die Gebietsdomäne umetikettiert.
  Statistics (#128), Polygons (#129) und Host-Primitives bleiben hinter einem
  engen, dokumentierten Strangler-Adapter.

## Lessons learned für #108

Einfach waren Manifest, Router-Contribution, build-time Nuxt-Routen, Navigation
und deklarative Map-Definitionen. Der bestehende öffentliche API-Prefix lässt sich
direkt am Module API Port erhalten; ein Module-Prefix ist keine Voraussetzung.

Im SDK fehlte ein ausdrücklicher Vertrag zur Adoption bestehender Tabellen. Der
additive `adopted_tables`-Wert schließt diese Lücke generisch: Er erlaubt exakt
benannte Tabellen außerhalb des künftigen Modulschemas, ohne DDL auszuführen oder
die konservative Fremdtabellenprüfung abzuschalten.

Die aufwendigen Teile waren nicht Gebietsliste oder Hierarchie, sondern die heute
im selben Router gebündelten fremden Verträge. Für weitere Migrationen sollte #108
vor dem Router-Umzug Request-Session-, Public-Query-Guard- und Map-Preview-Ports
bereitstellen. Statistics, Analytics und Polygons benötigen eigene öffentliche
Services, damit der temporäre Adapter wieder schrumpft. Frontendseitig sollten
fachliche Stores und Selection Presentations als nächster Schritt vollständig über
das Map SDK konsumierbar werden; deklarative Layer allein ersetzen noch keine
fachliche Auswahlzustandsmigration. Komponenten für dynamische UI-Contributions
müssen im Layer global registriert werden, weil ihr Name erst zur Laufzeit aus dem
Manifest aufgelöst wird. Karteninteraktionen brauchen außerdem eine gemeinsame
priorisierte Registry inklusive generischem Clear-Fallback, damit Host- und
Modul-Features bei überlappenden Geometrien nicht konkurrieren.

Die Pilotregel lautet deshalb: zuerst URLs und Verhalten charakterisieren, dann
Ownership festlegen, erst danach Dateien verschieben. Baseline-Ausnahmen bleiben
datei- und importgenau, haben ein Tracking-Issue und dürfen in Folge-PRs nur
kleiner werden.
