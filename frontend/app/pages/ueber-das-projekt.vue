<template>
  <article class="mx-auto max-w-5xl px-5 py-12 sm:px-6 lg:px-8">
    <p class="mb-3 text-xs font-bold uppercase text-[#687176]">Projekt</p>
    <h1 class="max-w-3xl text-3xl font-bold text-[#202427]">Über das Projekt</h1>
    <p class="mt-4 max-w-3xl text-base leading-7 text-[#4f575c]">
      Open City Map ist eine interaktive GIS-Anwendung für die Flensburger Innenstadt. Das Projekt macht Verkaufsflächen, Branchen, Leerstände und räumliche Kennzahlen direkt auf einer Karte erfassbar, bearbeitbar und auswertbar.
    </p>

    <div class="mt-10 grid gap-10">
      <section class="grid gap-4 border-t border-[#dfe3e4] pt-8 md:grid-cols-[220px_minmax(0,1fr)]">
        <h2 class="text-lg font-bold text-[#202427]">Ziel</h2>
        <div class="space-y-4 text-sm leading-6 text-[#4f575c]">
          <p>
            Die Anwendung unterstützt die strukturierte Beobachtung innerstädtischer Lagen. Statt Verkaufsflächen nur als Tabelle oder Bericht zu betrachten, werden sie als konkrete Geometrien auf der Karte geführt. Dadurch lassen sich Lage, Größe, Nutzung und Veränderung einer Fläche unmittelbar räumlich einordnen.
          </p>
          <p>
            Der Fokus liegt auf einem praktischen Werkzeug für Stadtanalyse, Open-Data-Arbeit, Leerstandsmonitoring und die Diskussion über Innenstadtentwicklung. Die Oberfläche ist so aufgebaut, dass Flächen schnell gefunden, gefiltert, gezeichnet, ausgewählt und fachlich eingeordnet werden können.
          </p>
        </div>
      </section>

      <section class="grid gap-4 border-t border-[#dfe3e4] pt-8 md:grid-cols-[220px_minmax(0,1fr)]">
        <h2 class="text-lg font-bold text-[#202427]">Kartenarbeit</h2>
        <div class="space-y-4 text-sm leading-6 text-[#4f575c]">
          <p>
            Im Mittelpunkt steht eine MapLibre-Karte mit OpenStreetMap-basierten Vektorkacheln. Bestehende Beispiel- und Nutzflächen werden farblich nach Branche dargestellt. Eigene Flächen können als Polygone angelegt, ausgewählt, bearbeitet und gelöscht werden.
          </p>
          <p>
            Beim Bearbeiten einer Fläche können Geometrie und Eigenschaften zusammen gepflegt werden: Flächentyp, Größenklasse und Etage. Die Farbe einer Fläche folgt dem gewählten Flächentyp, damit Nutzungen wie Mode, Gastronomie, Warenhaus, Technik oder sonstige Flächen visuell unterscheidbar bleiben.
          </p>
        </div>
      </section>

      <section class="grid gap-4 border-t border-[#dfe3e4] pt-8 md:grid-cols-[220px_minmax(0,1fr)]">
        <h2 class="text-lg font-bold text-[#202427]">Filter</h2>
        <div class="space-y-4 text-sm leading-6 text-[#4f575c]">
          <p>
            Die linke Seitenleiste dient der Auswahl der sichtbaren Flächen. Nach Branchen lassen sich einzelne Nutzungskategorien ein- und ausblenden. Die Größenklassen S, M, L und XL beschreiben interne Verkaufsflächenklassen, mit denen Flächen unabhängig von exakten Quadratmeterwerten vergleichbar werden.
          </p>
          <p>
            Die Etagenfilter UG, EG und OG grenzen die Anzeige nach Lage im Gebäude ein. Besonders für Innenstadtlagen ist das Erdgeschoss oft entscheidend, während Untergeschoss und Obergeschoss andere Nutzungsprofile haben können.
          </p>
        </div>
      </section>

      <section class="grid gap-4 border-t border-[#dfe3e4] pt-8 md:grid-cols-[220px_minmax(0,1fr)]">
        <h2 class="text-lg font-bold text-[#202427]">Analyse</h2>
        <div class="space-y-4 text-sm leading-6 text-[#4f575c]">
          <p>
            Die rechte Seitenleiste zeigt Kennzahlen zur aktuellen Karte und zur ausgewählten Fläche. Ohne Auswahl werden allgemeine Fast Facts, die Branchenverteilung und eine Miettabelle angezeigt. Bei einer ausgewählten Fläche berechnet das Backend räumliche Werte wie Fläche, Umfang und Mittelpunkt.
          </p>
          <p>
            Einzelne Branchen können über das Diagramm hervorgehoben werden. So wird sichtbar, welche Nutzungen in der Karte dominieren und wo sie räumlich liegen.
          </p>
          <p class="rounded-md bg-[#f4f7f8] p-4 text-[#3f484d]">
            Einige Kennzahlen wie Shops, Leerstand, Filialisierung, Zentralität, Kaufkraft und Spitzenmieten sind im aktuellen Stand Demonstrations- beziehungsweise Konfigurationswerte. Sie markieren die spätere analytische Oberfläche und sollten vor einem produktiven Einsatz durch belastbare Quellen ersetzt werden.
          </p>
        </div>
      </section>

      <section class="grid gap-4 border-t border-[#dfe3e4] pt-8 md:grid-cols-[220px_minmax(0,1fr)]">
        <h2 class="text-lg font-bold text-[#202427]">Technik</h2>
        <div class="space-y-4 text-sm leading-6 text-[#4f575c]">
          <p>
            Das Frontend basiert auf Nuxt 4, Vue, Pinia, TailwindCSS, MapLibre GL und Terra Draw. Die Kartenquelle ist über Nuxt Runtime Config austauschbar und verweist standardmäßig auf einen VersaTiles-Stil.
          </p>
          <p>
            Das Backend stellt eine FastAPI-Schnittstelle für Polygone und Geometrieauswertungen bereit. PostgreSQL mit PostGIS speichert die Geometrien und ermöglicht räumliche Berechnungen. Die API arbeitet mit GeoJSON, damit Frontend, Karte und Datenbank über ein etabliertes Geodatenformat gekoppelt bleiben.
          </p>
        </div>
      </section>

      <section class="grid gap-4 border-t border-[#dfe3e4] pt-8 md:grid-cols-[220px_minmax(0,1fr)]">
        <h2 class="text-lg font-bold text-[#202427]">Offenheit</h2>
        <div class="space-y-4 text-sm leading-6 text-[#4f575c]">
          <p>
            Open City Map ist als offenes, nachvollziehbares Werkzeug gedacht. Die Anwendung trennt Kartenanzeige, Fachdaten, Geometrievalidierung und rechtliche Betreiberangaben klar voneinander. Dadurch kann sie an andere Gebiete, Datenquellen oder kommunale Fragestellungen angepasst werden.
          </p>
          <p>
            Für den Produktivbetrieb sollten Zuständigkeiten, Datenquellen, Aktualisierungsprozesse und Löschfristen verbindlich dokumentiert werden. Die technische Grundlage ist darauf vorbereitet, reale Daten schrittweise anstelle der Demo- und Konfigurationswerte einzubinden.
          </p>
        </div>
      </section>
    </div>
  </article>
</template>

<script setup lang="ts">
import { buildWebPageStructuredData } from '~/utils/seo'

const config = useRuntimeConfig()
const description = 'Ausführliche Projektbeschreibung der Open City Map für Flensburg mit Kartenfunktionen, Analyse, Datenmodell und Technik.'
usePageSeo({
  title: 'Über das Projekt',
  description,
  path: '/ueber-das-projekt',
  structuredData: buildWebPageStructuredData(config.public.siteUrl, '/ueber-das-projekt', 'Über das Projekt', description)
})
</script>
