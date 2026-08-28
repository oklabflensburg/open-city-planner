# Frontend UI Contributions

Frontend-Module können dem Host deklarative Navigation und lokale Vue-Komponenten
bereitstellen. Die Architekturentscheidung steht im
[ADR zu Frontend UI Extension Points](../architecture/adr-frontend-ui-extension-points.md).

## Öffentlicher Contract

Das öffentliche SDK wird über `#frontend-module-sdk` exportiert. Die wichtigsten
Typen sind `UiSlotId`, `FrontendModuleUiContribution`, `NavigationContribution`,
`HeaderActionContribution`, `UiVisibilityRule` und `UiVisibilityContext`.
`FRONTEND_MODULE_SDK_VERSION` ist additiv `1.4.0`; die UI-Verträge aus
Versionen `1.1.0` bis `1.3.0` bleiben unverändert kompatibel. Die zusätzlichen
Platform-Ports sind separat unter
[Frontend-Platform-Ports](frontend-platform-ports.md) beschrieben.

Unterstützte Slots:

| Slot | Payload | Aktueller Host-Renderer |
| --- | --- | --- |
| `navigation.primary` | Navigation | Desktop, Mobil und Footer |
| `navigation.user` | Navigation | Account-Menü bei Anmeldung |
| `navigation.admin` | Navigation | berechtigungsgefiltertes Account-Menü |
| `header.actions` | lokale Vue-Komponente mit Accessible Label | Desktop-Header |
| `sidebar` | lokale Vue-Komponente | Contract für spätere Shell-Erweiterung |
| `dashboard.widgets` | lokale Vue-Komponente | Contract für ein späteres Dashboard |
| `profile.sections` | lokale Vue-Komponente | Contract für spätere Profilbereiche |
| `map.controls` | lokale Vue-Komponente mit Accessible Label | Kartenhost aus #103 |
| `map.layers` | lokale Vue-Komponente | Layer-Bedienelemente in der Karten-Seitenleiste |
| `map.selection` | lokale Vue-Komponente | Details der aktuellen Modulauswahl |
| `map.bottomSheet` | lokale Vue-Komponente | für #103 reserviert |
| `map.contextMenu` | lokale Vue-Komponente | für #103 reserviert |

Die letzten acht Slots definieren stabile Payloads; nicht gerenderte reservierte
Slots erzwingen dabei keine
neue Host-Layout- oder Map-Runtime.

## Manifest-Beispiel

```json
{
  "publicContributions": {
    "routes": [
      {
        "path": "/module-example",
        "source": "layer/app/pages/module-example.vue"
      }
    ],
    "ui": [
      {
        "id": "example-module.primary-navigation",
        "slot": "navigation.primary",
        "priority": 250,
        "label": "Beispielmodul",
        "to": "/module-example",
        "exact": true
      },
      {
        "id": "example-module.header-action",
        "slot": "header.actions",
        "component": "ExampleModuleAction",
        "source": "layer/app/components/ExampleModuleAction.vue",
        "accessibleLabel": "Frontend-Modulbeispiel öffnen"
      }
    ]
  }
}
```

Der Host leitet `moduleId` aus dem bereits validierten Modul ab. Ein Modul kann
diese Ownership nicht überschreiben. Statische Navigation muss auf eine bekannte
Host- oder aktivierte Modulroute zeigen. Component-Quellen müssen innerhalb des
eigenen `layer/app/components`-Verzeichnisses liegen.

## IDs und Reihenfolge

Contribution-IDs folgen `<module-id>.<beitragsname>` und bleiben über Releases
stabil. Doppelte IDs stoppen den Preflight und nennen beide Module und Slots.

Die globale Sortierung lautet:

1. `priority`, kleinere Zahl zuerst; Standard ist `100`;
2. deterministische Dependency-/Modulreihenfolge aus #101;
3. Contribution-ID als stabiler Tie-Breaker.

Hostnavigation und Modulnavigation werden anschließend mit denselben Regeln zu
einer Liste zusammengesetzt. Active Styling, `aria-current` und responsive
Darstellung bleiben Aufgabe des Hosts.

## Visibility

Eine Regel kann folgende einfache Felder kombinieren:

```json
{
  "auth": "authenticated",
  "permission": "platform.superuser",
  "feature": "mein-modul.preview",
  "module": "mein-modul"
}
```

- Ohne `auth` gilt `public`; außerdem sind `authenticated` und `anonymous` möglich.
- Unbekannte Permission-Identifier werden standardmäßig verweigert.
- Feature-Identifier verwenden einen kleinen Resolver; #102 führt keine eigene
  Feature-Flag-Plattform ein.
- Modulzustand basiert auf dem immutable Build-Inventar.

Visibility muss für Server und Hydration denselben Zustand verwenden. Sie ist kein
Ersatz für Backend-Autorisierung und darf nie den alleinigen Schutz vertraulicher
Daten oder Aktionen bilden.

## Component Contributions

Components werden im lokalen Nuxt Layer gebaut und durch ihren registrierten
PascalCase-Namen referenziert. Props sind auf JSON-sichere Werte begrenzt. Nicht
erlaubt sind HTML-Strings, Script-Injection, Remote-URLs, Runtime-Eval, iframes als
Modulmechanismus und Deep Imports in fremde Module oder private Hostdateien.

Module können die vorhandenen globalen Primitives `Button`, `Card`, `StatusBadge`
und `AppModal` sowie normale Vue-/Nuxt-Autoimports verwenden. Neue öffentliche
Host-APIs werden ausschließlich additiv über `#frontend-module-sdk` eingeführt.

## Accessibility-Verantwortung

| Host | Modul |
| --- | --- |
| Landmark- und Navigationssemantik | verständliche sichtbare und Accessible Labels |
| Reihenfolge und aktiver Link | interne Component-Semantik |
| Keyboard-Erreichbarkeit und Focus Styles | Form- und Eingabelabels |
| Öffnen, Schließen und Focus-Verhalten der Shell | keine Keyboard Traps |
| Desktop-/Mobile-Platzierung | keine Abhängigkeit von Host-Breakpoints |

## Example-Modul und deaktivierter Zustand

`example-module` registriert einen Primary-Link, einen permission-sensitiven
Adminlink und `ExampleModuleAction` in `header.actions`. Der Host importiert keine
dieser Dateien und kennt die Modul-ID nicht. Mit leerem `OCP_FRONTEND_MODULES`
werden weder Layer, Links noch Component-Snapshot gebaut.

Die Map-Slots werden durch den Kartenhost aus #103 gerendert. Source-, Layer-,
Control-, Draw- und Interaction-Verträge stehen im [Map SDK](map-sdk.md); die
vollständige Permission-Registry folgt in #104.
