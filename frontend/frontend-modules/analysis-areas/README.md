# Analysis Areas frontend module

Dieses lokale Nuxt-Layer besitzt die bestehenden öffentlichen Routen `/gebiete`
und `/gebiete/:slug`, den primären Navigationseintrag sowie die deklarative
GeoJSON-Quelle und Gebietslayer. URLs, SSR-Inhalte, Canonical, OpenGraph,
Structured Data und Breadcrumbs bleiben unverändert.

`AnalysisAreasMapRuntime` lädt die bestehende API über den vorhandenen Store,
aktualisiert ausschließlich die module-owned Map-SDK-Quelle und registriert
Interaktion und FeatureInfo. `MapCanvas.vue` importiert das Modul nicht.

Ohne `OCP_FRONTEND_MODULES=analysis-areas` werden Layer, Control, Navigation und
beide Seiten nicht in den Build aufgenommen. Die Backend-Daten bleiben davon
unberührt.
