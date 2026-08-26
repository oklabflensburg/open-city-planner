# ADR: Frontend UI Extension Points

- Status: Angenommen
- Datum: 2026-08-26
- Entscheidung: [Issue #102](https://github.com/oklabflensburg/open-city-planner/issues/102)
- Grundlage: [Issue #101](https://github.com/oklabflensburg/open-city-planner/issues/101) / PR #143
- Epic: [Issue #91](https://github.com/oklabflensburg/open-city-planner/issues/91)

## Kontext

#101 integriert lokale Frontend-Module deterministisch als Nuxt Layers. Ohne einen
öffentlichen UI-Contract müssten Module zentrale Header-, Navigations- oder
Profilkomponenten dennoch fachlich patchen. Das würde den Host erneut an konkrete
Module koppeln und spätere Fachmigrationen erschweren.

Der aktuelle Host besitzt eine gemeinsame Hauptnavigation für Desktop, Mobil und
Footer. Benutzer- und Adminlinks werden im Account-Menü zusammengesetzt. Es gibt
noch kein allgemeines Dashboard- oder Sidebar-Layout. Die Map hat eigene GIS-
Panels, deren fachliche Extension API erst #103 definiert.

## Entscheidung

Der Frontend-Modulcontract wird additiv um deklarative UI Contributions erweitert.
Die SDK-Version steigt gemäß der in #101 festgelegten SemVer-Regel von `1.0.0` auf
`1.1.0`. Module beschreiben Navigation oder lokale Komponenten in ihrer
`module.json`; sie erhalten keine allgemeine imperative `setup()`-Funktion und
keinen unkontrollierten Host-Kontext.

Der host-owned `FrontendContributionRegistry` bindet bei der Registrierung die
Modul-ID, validiert Struktur und Ownership, weist eine deterministische
Modulreihenfolge zu und wird vor dem Rendering versiegelt:

```text
lokale Modulmanifeste
        |
        v
Build-Time Discovery und Modulreihenfolge
        |
        v
Contribution Registration -> Validation -> Seal
        |
        v
immutable Build-Snapshot im Nuxt Runtime Config
        |
        v
SSR-sichere Visibility -> Host Renderer
```

Kleinere `priority`-Werte werden zuerst gerendert. Bei gleicher Priorität folgen
die Dependency-/Modulreihenfolge aus #101 und danach die stabile Contribution-ID.
IDs sind global eindeutig und beginnen mit `<module-id>.`. Zufällige UUIDs und
Component-Namen als alleinige Identität sind unzulässig.

## Slots und Payloads

Die stabilen Slot-IDs sind eine TypeScript-Literal-Union:

- `navigation.primary`, `navigation.user`, `navigation.admin` verwenden sichere
  Navigation-Descriptoren mit Label, internem Pfad und optionalem Exact-Matching;
- `header.actions`, `sidebar`, `dashboard.widgets` und `profile.sections` verwenden
  lokale Component-Descriptoren;
- `map.controls`, `map.bottomSheet` und `map.contextMenu` reservieren ausschließlich
  generische Vue-UI-Flächen für #103.

Es gibt keinen HTML-String-Payload, keine Remote-Komponente, keine URL-Imports und
keine Auswertung von JavaScript-Strings. Component-Quellen müssen im eigenen
Nuxt-Layer unter `app/components` liegen. Der Preflight verbietet direkte Imports
aus fremden Modulen und private `~/`-/`@/`-Hostimporte. Das Alias
`#frontend-module-sdk` ist der stabile öffentliche TypeScript-Einstieg. Die bereits
globalen Host-Komponenten `Button`, `Card`, `StatusBadge` und `AppModal` bleiben die
bewusst freigegebenen UI-Primitives; weitere Freigaben benötigen eine additive
SDK-Entscheidung.

## Visibility und Sicherheit

Visibility ist getrennt von der statischen Definition. Der kleine deklarative
Contract unterstützt `public`, `authenticated` und `anonymous` sowie optionale
Permission-, Feature- und Modulzustands-Identifier. Ohne Regel ist ein Beitrag
sichtbar. Unbekannte Permissions und Features werden standardmäßig verweigert.
Aktuell adaptiert der Host nur `platform.verwaltung` und `platform.superuser` an
die bestehenden Auth-Primitives. #104 kann den Resolver später ersetzen, ohne
Manifest-Payloads zu ändern.

Visibility ist ausschließlich Darstellung und niemals Autorisierung. Backend-
Endpoints, Daten und Mutationen müssen weiterhin serverseitig geschützt sein. Der
Registry-Snapshot enthält keine Secrets oder ungefilterten Environment-Werte.

Der Modulzustand stammt primär aus dem Build-Time-Enablement: Ein deaktivierter
Layer besitzt weder Code noch Contributions im Build. Optionale Visibility-
Abhängigkeiten auf weitere aktivierte Module werden gegen denselben immutable
Build-Snapshot ausgewertet.

## SSR und Hydration

Registration geschieht nicht in `onMounted`, sondern vollständig vor dem Nuxt-
Build. Server und Client erhalten denselben sortierten Snapshot. Nur die
Sichtbarkeit wird aus SSR-/Hydration-stabilem Auth- und Hostzustand ausgewertet;
es gibt keine zufälligen IDs, Zeitwerte oder mutable globale Registry. Die
Pinia-Auth-Instanz bleibt Host-owned, die Registry selbst besitzt keinen Store.

## Accessibility und Responsive Ownership

Der Host verantwortet Landmark- und Navigationssemantik, Reihenfolge, aktiven Link,
Focus Styles, Keyboard-Erreichbarkeit, Menü-Schließen und responsive Platzierung.
Ein Primary-Beitrag erscheint durch dieselbe Liste in Desktop- und Mobile-
Navigation; Module kennen keine Host-Breakpoints.

Module verantworten verständliche Labels, die interne Semantik ihrer Komponente,
Form-Labels und das Vermeiden von Keyboard Traps. `header.actions` verlangt
zusätzlich ein `accessibleLabel`, das der Host an die gerenderte Komponente bindet.

## Grenzen

#102 migriert keine bestehende Fachdomäne. Vorhandene Hostlinks bleiben zunächst
erhalten und werden mit Modulbeiträgen zusammengesetzt. Ein generischer Renderer
beweist `header.actions`; Slots ohne aktuelle Hostfläche werden nicht durch eine
neue Layout Engine erzwungen.

Insbesondere entstehen keine MapLibre Source-/Layer-Registry, Feature-Query-,
Draw-, Interaction- oder Map-State-API. Diese gehören zu #103. Ebenso entsteht
keine vollständige Permission Registry oder Feature-Flag-Plattform; diese Adapter
sind bewusst klein für #104 vorbereitet.
