<template>
  <ContentPageShell
    title="Open Data & Civic Tech"
    :description="description"
    eyebrow="OK Lab Flensburg"
    :breadcrumbs="[{ label: 'Startseite', to: '/' }, { label: 'Open Data' }]"
    max-width="wide"
  >
    <Card class="overflow-hidden">
      <div class="grid items-center gap-6 p-5 sm:p-7 lg:grid-cols-[minmax(0,1fr)_18rem] lg:p-9">
        <div>
          <p class="text-sm font-bold uppercase tracking-[0.16em] text-[#154d73]">Lokale Projekte, offene Daten</p>
          <h2 class="mt-2 text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">Technologie für eine offene Stadt</h2>
          <p class="mt-4 max-w-3xl leading-7 text-slate-600">
            Das OK Lab Flensburg ist eine ehrenamtliche Community aus der Region und Teil des Code-for-Germany-Netzwerks lokaler Open-Knowledge-Labs. Gemeinsam entstehen Anwendungen und Prototypen, die öffentliche Informationen verständlich, auffindbar und nutzbar machen.
          </p>
          <div class="mt-6 flex flex-wrap gap-3">
            <a :href="sourceUrl" target="_blank" rel="noopener noreferrer" class="page-button-primary">
              OK Lab kennenlernen <ExternalLink class="size-4" aria-hidden="true" />
            </a>
            <a href="https://github.com/oklabflensburg" target="_blank" rel="noopener noreferrer" class="page-button-secondary">
              <Github class="size-4" aria-hidden="true" /> GitHub
            </a>
          </div>
        </div>
        <div class="mx-auto rounded-3xl border border-slate-200 bg-slate-50 p-6 shadow-inner">
          <img src="/branding/ok-lab-flensburg.svg" width="180" height="180" alt="Logo des OK Lab Flensburg" class="size-40 sm:size-44">
        </div>
      </div>
      <dl class="grid border-t border-slate-200 bg-slate-50 sm:grid-cols-3">
        <div class="p-5 text-center"><dt class="text-sm font-semibold text-slate-600">Projekte</dt><dd class="mt-1 text-2xl font-bold text-slate-950">{{ okLabProjects.length }}</dd></div>
        <div class="border-y border-slate-200 p-5 text-center sm:border-x sm:border-y-0"><dt class="text-sm font-semibold text-slate-600">Kategorien</dt><dd class="mt-1 text-2xl font-bold text-slate-950">{{ okLabProjectCategories.length }}</dd></div>
        <div class="p-5 text-center"><dt class="text-sm font-semibold text-slate-600">Offene Repositories</dt><dd class="mt-1 text-2xl font-bold text-slate-950">{{ okLabProjects.length }}</dd></div>
      </dl>
    </Card>

    <ContentSection
      class="mt-10"
      title="Was Open Data und Civic Tech bewirken"
      description="Offene Daten werden besonders wertvoll, wenn Menschen sie prüfen, verbinden und in verständliche Werkzeuge übersetzen. Civic Tech macht daraus konkrete digitale Angebote für Alltag, Beteiligung und Verwaltung."
    >
      <div class="grid gap-4 md:grid-cols-3">
        <Card v-for="item in principles" :key="item.title" class="p-5 sm:p-6">
          <component :is="item.icon" class="size-6 text-[#154d73]" aria-hidden="true" />
          <h3 class="mt-4 font-bold text-slate-950">{{ item.title }}</h3>
          <p class="mt-2 text-sm leading-6 text-slate-600">{{ item.text }}</p>
        </Card>
      </div>
    </ContentSection>

    <ContentSection
      id="projekte"
      class="mt-12"
      title="Projekte des OK Lab Flensburg"
      description="Die Übersicht basiert auf den aktuellen Projektseiten bei Code for Germany. Suche frei oder grenze die Auswahl nach Kategorie ein."
    >
      <OpenDataProjectFilters
        v-model:search="search"
        v-model:category="category"
        :categories="okLabProjectCategories"
        @reset="resetFilters"
      />

      <p class="mt-5 text-sm font-semibold text-slate-600" aria-live="polite">
        {{ filteredProjects.length }} {{ filteredProjects.length === 1 ? 'Projekt' : 'Projekte' }} gefunden
      </p>

      <div v-if="filteredProjects.length" class="mt-4 grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        <OpenDataProjectCard v-for="project in filteredProjects" :key="project.slug" :project="project" />
      </div>
      <Card v-else class="mt-4 p-8 text-center sm:p-12">
        <SearchX class="mx-auto size-9 text-slate-400" aria-hidden="true" />
        <h3 class="mt-4 text-lg font-bold text-slate-950">Keine passenden Projekte</h3>
        <p class="mt-2 text-sm text-slate-600">Ändere den Suchbegriff oder setze die Filter zurück.</p>
        <Button class="mt-5" @click="resetFilters">Filter zurücksetzen</Button>
      </Card>
    </ContentSection>

    <Card class="mt-12 overflow-hidden border-[#b8d3e3] bg-[#edf4f8]">
      <div class="grid gap-5 p-6 sm:p-8 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
        <div>
          <h2 class="text-xl font-bold text-slate-950 sm:text-2xl">Mitmachen beim OK Lab Flensburg</h2>
          <p class="mt-2 max-w-3xl leading-7 text-slate-700">Ideen, Datenfragen, Gestaltung und Code sind willkommen. Vorkenntnisse sind nicht erforderlich; die Community trifft sich mittwochs in Flensburg.</p>
        </div>
        <a :href="sourceUrl" target="_blank" rel="noopener noreferrer" class="page-button-primary">
          Termine und Kontakt <ExternalLink class="size-4" aria-hidden="true" />
        </a>
      </div>
    </Card>

    <aside class="mt-8 rounded-2xl border border-slate-200 bg-white p-5 text-sm leading-6 text-slate-600 sm:p-6" aria-label="Quellen- und Lizenzhinweis">
      <p><strong class="text-slate-800">Quelle und Stand:</strong> Projektinformationen nach <a :href="sourceUrl" target="_blank" rel="noopener noreferrer" class="font-semibold text-[#154d73] underline underline-offset-2">Code for Germany / OK Lab Flensburg</a>, geprüft am {{ sourceDateGerman }}.</p>
      <p class="mt-2">Die lokal optimierten Vorschaubilder stammen von den jeweiligen Projektseiten. Dort ist keine abweichende Kennzeichnung ausgewiesen; Code for Germany stellt Inhalte und Texte, sofern nicht anders angegeben, unter <a :href="licenseUrl" target="_blank" rel="license noopener noreferrer" class="font-semibold text-[#154d73] underline underline-offset-2">CC BY 4.0</a>. Die Beschreibungen auf dieser Seite sind eigenständige Kurzfassungen.</p>
    </aside>
  </ContentPageShell>
</template>

<script setup lang="ts">
import { Database, ExternalLink, Github, Handshake, SearchX, Shapes } from 'lucide-vue-next'
import {
  filterOKLabProjects,
  OK_LAB_PROJECT_LICENSE_URL,
  OK_LAB_PROJECT_SOURCE_DATE,
  OK_LAB_PROJECT_SOURCE_URL,
  okLabProjectCategories,
  okLabProjects
} from '~/config/okLabProjects'
import { buildAbsoluteUrl } from '~/utils/seo'

const config = useRuntimeConfig()
const search = ref('')
const category = ref('')
const sourceUrl = OK_LAB_PROJECT_SOURCE_URL
const licenseUrl = OK_LAB_PROJECT_LICENSE_URL
const sourceDateGerman = new Intl.DateTimeFormat('de-DE', { dateStyle: 'long' }).format(new Date(`${OK_LAB_PROJECT_SOURCE_DATE}T12:00:00Z`))
const description = 'Entdecke 18 offene Civic-Tech-Projekte des OK Lab Flensburg – mit Karten, Datenquellen, Websites und frei zugänglichem Quellcode.'
const filteredProjects = computed(() => filterOKLabProjects(okLabProjects, search.value, category.value))
const principles = [
  { title: 'Daten zugänglich machen', text: 'Öffentliche Datensätze werden auffindbar, nachvollziehbar und für neue Anwendungen nutzbar.', icon: Database },
  { title: 'Gemeinsam gestalten', text: 'Menschen aus Technik, Design, Verwaltung und Zivilgesellschaft bringen verschiedene Perspektiven ein.', icon: Handshake },
  { title: 'Prototypen erproben', text: 'Offene Karten und Werkzeuge zeigen konkret, wie digitale öffentliche Angebote aussehen können.', icon: Shapes }
]

function resetFilters() {
  search.value = ''
  category.value = ''
}

const pageUrl = buildAbsoluteUrl(config.public.siteUrl, '/open-data')
const structuredProjects = okLabProjects.map((project, index) => ({
  '@type': 'ListItem',
  position: index + 1,
  item: {
    '@type': 'SoftwareApplication',
    name: project.title,
    description: project.description,
    url: project.websiteUrl || project.codeForGermanyUrl,
    codeRepository: project.githubUrl,
    image: project.thumbnail ? buildAbsoluteUrl(config.public.siteUrl, project.thumbnail) : undefined,
    applicationCategory: 'CivicTechApplication'
  }
}))

usePageSeo({
  title: 'Open Data & Projekte des OK Lab Flensburg',
  description,
  path: '/open-data',
  image: okLabProjects[0]?.thumbnail,
  imageAlt: 'Wohnort-Kompass des OK Lab Flensburg',
  structuredData: [
    {
      '@context': 'https://schema.org',
      '@type': 'CollectionPage',
      name: 'Open Data & Projekte des OK Lab Flensburg',
      description,
      url: pageUrl,
      mainEntity: { '@id': `${pageUrl}#projekte` }
    },
    {
      '@context': 'https://schema.org',
      '@type': 'ItemList',
      '@id': `${pageUrl}#projekte`,
      name: 'Projekte des OK Lab Flensburg',
      numberOfItems: okLabProjects.length,
      itemListElement: structuredProjects
    }
  ]
})
</script>
