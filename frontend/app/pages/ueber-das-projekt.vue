<template>
  <ContentPageShell
    title="Über das Projekt"
    :description="description"
    eyebrow="Projekt"
    :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: 'Über das Projekt' }]"
    max-width="content"
  >
    <div class="space-y-8 md:space-y-10">
      <Card class="p-5 sm:p-7">
        <p class="max-w-4xl text-base leading-7 text-slate-700">
          Stadtplaner ist eine interaktive GIS-Anwendung für die Flensburger Innenstadt. Verkaufsflächen werden als konkrete Geometrien auf der Karte geführt und lassen sich dadurch räumlich finden, einordnen und auswerten.
        </p>
        <div class="mt-6 flex flex-wrap gap-3">
          <NuxtLink class="page-button-primary" to="/">Karte öffnen <ArrowRight class="size-4" aria-hidden="true" /></NuxtLink>
          <NuxtLink class="page-button-secondary" to="/dokumentation">Dokumentation öffnen</NuxtLink>
        </div>
      </Card>

      <ContentSection title="Was ist Stadtplaner?">
        <div class="max-w-4xl space-y-4 leading-7 text-slate-700">
          <p>Die Anwendung unterstützt die strukturierte Beobachtung innerstädtischer Lagen. Statt Verkaufsflächen nur in Tabellen oder Berichten zu betrachten, verbindet sie Lage, Größe, Nutzung und Veränderungen direkt mit der Karte.</p>
          <p>Der Fokus liegt auf einem praktischen Werkzeug für Stadtanalyse, Open-Data-Arbeit, Leerstandsmonitoring und die Diskussion über Innenstadtentwicklung.</p>
        </div>
      </ContentSection>

      <ContentSection title="Was kann die Plattform?" description="Die Funktionen verbinden Kartenarbeit, strukturierte Flächendaten und räumliche Auswertung.">
        <div class="grid gap-4 sm:grid-cols-2">
          <article v-for="feature in features" :key="feature.title" class="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm">
            <component :is="feature.icon" class="size-5 text-[#154d73]" aria-hidden="true" />
            <h3 class="mt-4 font-bold text-slate-950">{{ feature.title }}</h3>
            <p class="mt-2 text-sm leading-6 text-slate-600">{{ feature.text }}</p>
          </article>
        </div>
      </ContentSection>

      <ContentSection title="Offene Daten und OpenStreetMap">
        <Card class="p-5 sm:p-7">
          <div class="max-w-4xl space-y-4 leading-7 text-slate-700">
            <p>Die Kartenbasis verwendet OpenStreetMap-basierte Vektorkacheln. Zu ausgewählten Flächen kann das Backend ergänzende öffentliche OpenStreetMap-Sachdaten aus einer lokalen PostGIS-Datenbank bereitstellen.</p>
            <p>Kartenanzeige, Fachdaten und Geometrievalidierung bleiben voneinander getrennt. OSM-Informationen sind im Stadtplaner ergänzend und schreibgeschützt; Änderungen an Flächen verändern OpenStreetMap nicht.</p>
          </div>
        </Card>
      </ContentSection>

      <ContentSection title="Technischer Hintergrund">
        <div class="grid gap-4 md:grid-cols-3">
          <Card v-for="group in technology" :key="group.title" class="p-5">
            <p class="text-xs font-bold uppercase tracking-wider text-slate-500">{{ group.title }}</p>
            <p class="mt-3 font-semibold leading-7 text-slate-900">{{ group.items }}</p>
          </Card>
        </div>
        <p class="mt-5 max-w-4xl leading-7 text-slate-700">Frontend, API und Datenbank tauschen Polygongeometrien im GeoJSON-Format aus. PostgreSQL mit PostGIS übernimmt Speicherung und räumliche Berechnungen; MapLibre rendert die interaktive Karte im Browser.</p>
      </ContentSection>

      <ContentSection title="OK Lab Flensburg">
        <Card class="grid gap-6 p-5 sm:grid-cols-[auto_minmax(0,1fr)] sm:items-center sm:p-7">
          <div class="w-fit rounded-xl border border-slate-200 bg-white p-3"><OKLabLogo size="footer" /></div>
          <div>
            <h3 class="font-bold text-slate-950">Ein Projekt des OK Lab Flensburg</h3>
            <p class="mt-2 max-w-3xl leading-7 text-slate-700">Das OK Lab Flensburg arbeitet mit offenen Daten, offenen Technologien und digitalen Werkzeugen für Flensburg. Die vorhandenen Kontakt- und Betreiberangaben finden Sie auf der Kontaktseite und im Impressum.</p>
            <NuxtLink class="mt-4 inline-flex font-bold text-[#154d73] hover:underline" to="/kontakt">Kontakt aufnehmen</NuxtLink>
          </div>
        </Card>
      </ContentSection>

      <ContentSection title="Open Source">
        <Card class="p-5 sm:p-7">
          <div class="max-w-4xl">
            <h3 class="text-lg font-bold text-slate-950">Offen entwickelt und nachvollziehbar</h3>
            <p class="mt-3 leading-7 text-slate-700">Der Quellcode des Stadtplaners ist öffentlich auf GitHub einsehbar. Dort lassen sich technische Umsetzung und Entwicklung nachvollziehen. Hinweise für Beiträge stehen in der CONTRIBUTING-Datei. Technische Fehler und Feature-Wünsche können über GitHub Issues gemeldet werden; für allgemeine Anfragen bleibt die Kontaktseite der richtige Weg.</p>
            <div class="mt-5 flex flex-col items-start gap-3 sm:flex-row sm:items-center">
              <GitHubLink variant="button" />
              <GitHubLink destination="contributing" label="Beitragen" />
              <GitHubLink destination="issues" label="Technischen Fehler melden" />
            </div>
          </div>
        </Card>
      </ContentSection>
    </div>
  </ContentPageShell>
</template>

<script setup lang="ts">
import { ArrowRight, BarChart3, Database, Map, Shapes } from 'lucide-vue-next'
import { projectConfig } from '~/config/project'
import { buildAbsoluteUrl, buildWebPageStructuredData } from '~/utils/seo'

const config = useRuntimeConfig()
const description = 'Stadtplaner verbindet interaktive Karten, Verkaufsflächen, offene Geodaten und räumliche Analysen für die Flensburger Innenstadt.'
const features = [
  { title: 'Interaktive Karte', text: 'Flächen nach Branche, Größenklasse und Etage finden, filtern und räumlich vergleichen.', icon: Map },
  { title: 'Polygonflächen', text: 'Angemeldete Nutzer können Flächen zeichnen; berechtigte Personen können Geometrie und Fachdaten pflegen.', icon: Shapes },
  { title: 'OpenStreetMap-Daten', text: 'Öffentliche OSM-Informationen aus der lokalen Geodatenbank ergänzen ausgewählte Flächendetails.', icon: Database },
  { title: 'Analysen', text: 'Kennzahlen, Branchenverteilung sowie berechnete Werte wie Fläche und Umfang unterstützen die Einordnung.', icon: BarChart3 }
]
const technology = [
  { title: 'Frontend', items: 'Nuxt 4 · Vue 3 · Pinia · TailwindCSS · MapLibre · Terra Draw' },
  { title: 'Backend', items: 'FastAPI · PostgreSQL · PostGIS' },
  { title: 'Geodaten', items: 'GeoJSON · OpenStreetMap · VersaTiles · Nominatim' }
]

usePageSeo({
  title: 'Über das Projekt',
  description,
  path: '/ueber-das-projekt',
  structuredData: [
    buildWebPageStructuredData(config.public.siteUrl, '/ueber-das-projekt', 'Über das Projekt', description),
    {
      '@context': 'https://schema.org',
      '@type': 'SoftwareSourceCode',
      name: projectConfig.name,
      codeRepository: projectConfig.github.url,
      url: buildAbsoluteUrl(config.public.siteUrl, '/'),
      programmingLanguage: ['TypeScript', 'Python']
    }
  ]
})
</script>
