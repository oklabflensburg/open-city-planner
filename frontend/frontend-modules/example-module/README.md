# Frontend-Example-Modul

Dieses rein technische Modul beweist die Build-Time-Integration aus #101. Es wird
nur mit `OCP_FRONTEND_MODULES=example-module` in den Nuxt-Build aufgenommen und
enthält keine Fachdomäne.
Es registriert deklarativ einen Eintrag in `navigation.primary`, einen
permission-sensitiven Admin-Eintrag und die lokale Komponente
`ExampleModuleAction` in `header.actions`.
Außerdem registriert das Modul eine kleine GeoJSON-Source und einen Circle-Layer
über das Map SDK. `MapCanvas.vue` kennt weder die Modul-ID noch den Layer;
deaktiviert ist die Kartenerweiterung nicht im Build-Snapshot.
