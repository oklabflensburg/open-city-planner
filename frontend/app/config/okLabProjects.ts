export type OKLabProjectStatus = 'in-progress' | 'completed' | 'contributors-wanted'

export interface OKLabProject {
  slug: string
  title: string
  category: string
  status: OKLabProjectStatus
  description: string
  codeForGermanyUrl: string
  websiteUrl: string | null
  githubUrl: string | null
  dataSourceUrl: string | null
  thumbnail: string | null
  thumbnailSourceUrl: string | null
}

export const OK_LAB_PROJECT_SOURCE_URL = 'https://codefor.de/flensburg/'
export const OK_LAB_PROJECT_SOURCE_DATE = '2026-08-13'
export const OK_LAB_PROJECT_LICENSE_URL = 'https://creativecommons.org/licenses/by/4.0/deed.de'

export const okLabProjectStatus: Record<OKLabProjectStatus, { label: string, tone: 'info' | 'success' | 'warning' }> = {
  'in-progress': { label: 'In Arbeit', tone: 'info' },
  completed: { label: 'Abgeschlossen', tone: 'success' },
  'contributors-wanted': { label: 'Mitwirkende gesucht', tone: 'warning' }
}

export const okLabProjects: OKLabProject[] = [
  {
    slug: 'wohnort-kompass',
    title: 'Wohnort-Kompass – Offene Daten für Regionen in Deutschland',
    category: 'Wohnen',
    status: 'in-progress',
    description: 'Vergleicht Gemeinden anhand persönlicher Prioritäten – von Klima und Mobilität bis Demografie, Flächennutzung und Erreichbarkeit.',
    codeForGermanyUrl: 'https://codefor.de/projekte/fl-open-living-map/',
    websiteUrl: 'https://wohnortkompass.oklabflensburg.de',
    githubUrl: 'https://github.com/oklabflensburg/open-living-map',
    dataSourceUrl: 'https://wohnortkompass.oklabflensburg.de/methodik',
    thumbnail: '/open-data/projects/wohnort-kompass.webp',
    thumbnailSourceUrl: 'https://codefor.de/projects/flensburg/screenshot_wohnortkompass.webp'
  },
  {
    slug: 'badestellenkarte-schleswig-holstein',
    title: 'Badestellenkarte Schleswig-Holstein',
    category: 'Freizeit',
    status: 'in-progress',
    description: 'Macht Badestellen und wassernahe Orte in Schleswig-Holstein auf einer filterbaren, interaktiven Karte zugänglich.',
    codeForGermanyUrl: 'https://codefor.de/projekte/fl-open-bath-map/',
    websiteUrl: 'https://badestellenkarte.oklabflensburg.de',
    githubUrl: 'https://github.com/oklabflensburg/open-bath-map',
    dataSourceUrl: 'https://opendata.schleswig-holstein.de/dataset/badegewasser-stammdaten-2026-04-01',
    thumbnail: '/open-data/projects/badestellenkarte.webp',
    thumbnailSourceUrl: 'https://codefor.de/projects/flensburg/screenshot_badestellenkarte.webp'
  },
  {
    slug: 'notfallkarte-schleswig-holstein',
    title: 'Notfallkarte Schleswig-Holstein',
    category: 'Gesellschaft',
    status: 'in-progress',
    description: 'Hilft dabei, Polizeidienststellen in Schleswig-Holstein schnell zu finden und die relevanten Standortinformationen einzusehen.',
    codeForGermanyUrl: 'https://codefor.de/projekte/fl-open-emergency-map/',
    websiteUrl: 'https://notfallkarte.oklabflensburg.de',
    githubUrl: 'https://github.com/oklabflensburg/open-emergency-map',
    dataSourceUrl: 'https://opendata.schleswig-holstein.de/collection/polizeidienststellen',
    thumbnail: '/open-data/projects/notfallkarte.webp',
    thumbnailSourceUrl: 'https://codefor.de/projects/flensburg/screenshot_notfallkarte.webp'
  },
  {
    slug: 'open-data-day-flensburg',
    title: '2. Open Data Day in Flensburg',
    category: 'Technologie',
    status: 'contributors-wanted',
    description: 'Bringt Interessierte bei Workshops, Präsentationen und offenem Austausch rund um Open Data und Civic Tech zusammen.',
    codeForGermanyUrl: 'https://codefor.de/projekte/fl-open-data-day/',
    websiteUrl: 'https://opendataday-flensburg.de',
    githubUrl: 'https://github.com/oklabflensburg/oddfl',
    dataSourceUrl: null,
    thumbnail: '/open-data/projects/open-data-day.webp',
    thumbnailSourceUrl: 'https://codefor.de/projects/flensburg/screenshot_opendataday_flensburg.webp'
  },
  {
    slug: 'flurstuecksauskunft-schleswig-holstein',
    title: 'Interaktive Flurstücksauskunft für Schleswig-Holstein',
    category: 'Verwaltung',
    status: 'in-progress',
    description: 'Zeigt Gemarkungen und Flurstücke ohne Eigentümerangaben in einer leicht zugänglichen, ausdrücklich nicht amtlichen Kartenansicht.',
    codeForGermanyUrl: 'https://codefor.de/projekte/fl-open-parcel-map/',
    websiteUrl: 'https://flurstuecksauskunft.oklabflensburg.de',
    githubUrl: 'https://github.com/oklabflensburg/open-parcel-map',
    dataSourceUrl: 'https://opendata.schleswig-holstein.de/dataset/alkis-schleswig-holstein-ohne-eigentumerangaben',
    thumbnail: '/open-data/projects/flurstuecksauskunft.webp',
    thumbnailSourceUrl: 'https://codefor.de/projects/flensburg/screenshot_flurstuecksauskunft.webp'
  },
  {
    slug: 'biotopkarte',
    title: 'Interaktive Biotopkarte mit Wert- und Nichtwertbiotopen',
    category: 'Naturschutz',
    status: 'in-progress',
    description: 'Visualisiert die Biotopkartierung Schleswig-Holsteins und macht geschützte wie weitere kartierte Lebensräume vergleichbar.',
    codeForGermanyUrl: 'https://codefor.de/projekte/fl-open-biotope-map/',
    websiteUrl: 'https://biotopkarte.oklabflensburg.de',
    githubUrl: 'https://github.com/oklabflensburg/open-biotope-map',
    dataSourceUrl: 'https://opendata.schleswig-holstein.de/dataset?tags=Biotopfl%C3%A4chen',
    thumbnail: '/open-data/projects/biotopkarte.webp',
    thumbnailSourceUrl: 'https://codefor.de/projects/flensburg/screenshot_biotopkarte.webp'
  },
  {
    slug: 'kulturnacht-karte',
    title: 'Karte der Veranstaltungsorte der Kulturnacht Flensburg',
    category: 'Kultur',
    status: 'completed',
    description: 'Bündelte die Veranstaltungsorte der Flensburger Kulturnacht 2024 in einer übersichtlichen digitalen Karte.',
    codeForGermanyUrl: 'https://codefor.de/projekte/fl-open-cultural-map/',
    websiteUrl: 'https://knf.grain.one',
    githubUrl: 'https://github.com/oklabflensburg/open-cultural-map',
    dataSourceUrl: null,
    thumbnail: '/open-data/projects/kulturnacht-karte.webp',
    thumbnailSourceUrl: 'https://codefor.de/projects/flensburg/screenshot_kulturkarte.webp'
  },
  {
    slug: 'bildungsatlas-flensburg',
    title: 'Bildungsatlas Flensburg',
    category: 'Gesellschaft',
    status: 'contributors-wanted',
    description: 'Ordnet Schulen räumlich ein und führt öffentlich verfügbare Angaben zu Schulform, Trägerschaft und Standort zusammen.',
    codeForGermanyUrl: 'https://codefor.de/projekte/fl-open-school-map/',
    websiteUrl: 'https://schulkarte.oklabflensburg.de',
    githubUrl: 'https://github.com/oklabflensburg/open-school-map',
    dataSourceUrl: 'https://www.statistik-nord.de/fileadmin/Dokumente/Verzeichnisse/Schulverzeichnis_A_22-23.pdf',
    thumbnail: '/open-data/projects/bildungsatlas.webp',
    thumbnailSourceUrl: 'https://codefor.de/projects/flensburg/screenshot_bildungsatlas.jpg'
  },
  {
    slug: 'kitafinder-flensburg',
    title: 'Kitafinder Flensburg',
    category: 'Gesellschaft',
    status: 'contributors-wanted',
    description: 'Erleichtert Familien die Orientierung, indem Kindertagesstätten mit wichtigen Informationen auf einer Karte zusammengeführt werden.',
    codeForGermanyUrl: 'https://codefor.de/projekte/fl-open-kita-map/',
    websiteUrl: 'https://kitakarte.oklabflensburg.de',
    githubUrl: 'https://github.com/oklabflensburg/open-kita-map',
    dataSourceUrl: 'https://www.flensburg.de/media/custom/2306_2545_1.PDF',
    thumbnail: '/open-data/projects/kitafinder.webp',
    thumbnailSourceUrl: 'https://codefor.de/projects/flensburg/screenshot_kitafinder_flensburg.jpg'
  },
  {
    slug: 'open-data-api',
    title: 'Open Data API',
    category: 'Gesellschaft',
    status: 'contributors-wanted',
    description: 'Stellt öffentliche Daten über eine gemeinsame Programmierschnittstelle für Kommunen, Initiativen und eigene Anwendungen bereit.',
    codeForGermanyUrl: 'https://codefor.de/projekte/fl-open-data-api/',
    websiteUrl: 'https://api.oklabflensburg.de',
    githubUrl: 'https://github.com/oklabflensburg/open-data-api',
    dataSourceUrl: null,
    thumbnail: '/open-data/projects/open-data-api.webp',
    thumbnailSourceUrl: 'https://codefor.de/projects/flensburg/screenshot_open_data_api.jpg'
  },
  {
    slug: 'nahverkehr-flensburg',
    title: 'Stadtplan mit dem Nahverkehr in Flensburg',
    category: 'Mobilität',
    status: 'contributors-wanted',
    description: 'Bereitet Haltestellen und Linien des Flensburger Nahverkehrs als offene, interaktive Kartendarstellung auf.',
    codeForGermanyUrl: 'https://codefor.de/projekte/fl-open-transport-map/',
    websiteUrl: 'https://nahverkehr.oklabflensburg.de',
    githubUrl: 'https://github.com/oklabflensburg/open-transport-map',
    dataSourceUrl: 'https://overpass-turbo.eu',
    thumbnail: '/open-data/projects/nahverkehrskarte.webp',
    thumbnailSourceUrl: 'https://codefor.de/projects/flensburg/screenshot_transport_map.jpg'
  },
  {
    slug: 'recyclingcontainer-flensburg',
    title: 'Karte der Recyclingcontainer in Flensburg',
    category: 'Gesellschaft',
    status: 'contributors-wanted',
    description: 'Zeigt städtische Standorte für Altglas- und Altkleidercontainer und macht die Entsorgungsmöglichkeiten besser auffindbar.',
    codeForGermanyUrl: 'https://codefor.de/projekte/fl-open-recycling-map/',
    websiteUrl: 'https://recycling.oklabflensburg.de',
    githubUrl: 'https://github.com/oklabflensburg/open-recycling-map',
    dataSourceUrl: null,
    thumbnail: '/open-data/projects/recyclingkarte.webp',
    thumbnailSourceUrl: 'https://codefor.de/projects/flensburg/screenshot-recycling-map.jpg'
  },
  {
    slug: 'sozialatlas-flensburg',
    title: 'Sozialatlas der Stadt Flensburg',
    category: 'Politik',
    status: 'contributors-wanted',
    description: 'Visualisiert sozialräumliche Kennzahlen als transparente Grundlage für kommunale Planung und öffentliche Diskussion.',
    codeForGermanyUrl: 'https://codefor.de/projekte/fl-open-social-map/',
    websiteUrl: 'https://sozialatlas.oklabflensburg.de',
    githubUrl: 'https://github.com/oklabflensburg/open-social-map',
    dataSourceUrl: 'https://www.flensburg.de/Leben-Soziales/Familie-Soziales/Sozialatlas',
    thumbnail: '/open-data/projects/sozialatlas.webp',
    thumbnailSourceUrl: 'https://codefor.de/projects/flensburg/screenshot_dashboard.jpg'
  },
  {
    slug: 'bodennutzung',
    title: 'Bodenfläche nach Art der Nutzung',
    category: 'Umwelt',
    status: 'contributors-wanted',
    description: 'Macht die Verteilung kommunaler Flächennutzungen sichtbar und ermöglicht Vergleiche zwischen Regionen und Gemeinden.',
    codeForGermanyUrl: 'https://codefor.de/projekte/fl-open-surface-map/',
    websiteUrl: 'https://bodennutzung.oklabflensburg.de',
    githubUrl: 'https://github.com/oklabflensburg/open-surface-map',
    dataSourceUrl: 'https://service.destatis.de/DE/karten/flaechenatlas2019daten.xlsx',
    thumbnail: '/open-data/projects/bodennutzung.webp',
    thumbnailSourceUrl: 'https://codefor.de/projects/flensburg/screenshot_surface_map.jpg'
  },
  {
    slug: 'strassenbaeume-flensburg',
    title: 'Straßenbäume der Stadt Flensburg',
    category: 'Umwelt',
    status: 'contributors-wanted',
    description: 'Macht den offenen Baumkataster der Stadt sichtbar und schafft einen einfachen Zugang zu Standorten und Baumdaten.',
    codeForGermanyUrl: 'https://codefor.de/projekte/fl-open-trees-map/',
    websiteUrl: 'https://baumkataster.oklabflensburg.de',
    githubUrl: 'https://github.com/oklabflensburg/open-trees-map',
    dataSourceUrl: 'https://opendata.schleswig-holstein.de/dataset/baumkataster-flensburg-2023-05-11',
    thumbnail: '/open-data/projects/baumkataster.webp',
    thumbnailSourceUrl: 'https://codefor.de/projects/flensburg/baumkataster_stadt_flensburg.png'
  },
  {
    slug: 'denkmalkarte-schleswig-holstein',
    title: 'Digitale Denkmalkarte für Schleswig-Holstein',
    category: 'Kultur',
    status: 'contributors-wanted',
    description: 'Stellt Kulturdenkmäler und ausgewählte Merkmale aus offenen Daten in einer interaktiven Kartenansicht dar.',
    codeForGermanyUrl: 'https://codefor.de/projekte/fl-open-monuments-map/',
    websiteUrl: 'https://denkmalkarte.oklabflensburg.de',
    githubUrl: 'https://github.com/oklabflensburg/open-monuments-map',
    dataSourceUrl: 'https://opendata.schleswig-holstein.de/organization/landesamt-fur-denkmalpflege',
    thumbnail: '/open-data/projects/denkmalkarte.webp',
    thumbnailSourceUrl: 'https://codefor.de/projects/flensburg/screenshot_denkmalkarte.webp'
  },
  {
    slug: 'spielplatzkarte-flensburg',
    title: 'Spielplatzkarte der Stadt Flensburg',
    category: 'Gesellschaft',
    status: 'contributors-wanted',
    description: 'Bereitet die Spielplatzstandorte des TBZ übersichtlich auf und erleichtert Familien die Suche nach passenden Spielflächen.',
    codeForGermanyUrl: 'https://codefor.de/projekte/fl-open-playgrounds-map/',
    websiteUrl: 'https://spielplatzkarte.oklabflensburg.de',
    githubUrl: 'https://github.com/oklabflensburg/open-playgrounds-map',
    dataSourceUrl: null,
    thumbnail: '/open-data/projects/spielplatzkarte.webp',
    thumbnailSourceUrl: 'https://codefor.de/projects/flensburg/spielplaetze_in_flensburg.jpg'
  },
  {
    slug: 'unfallkarte-flensburg',
    title: 'Unfallkarte der Stadt Flensburg',
    category: 'Mobilität',
    status: 'contributors-wanted',
    description: 'Visualisiert veröffentlichte Unfalldaten räumlich und unterstützt die Auseinandersetzung mit Verkehrssicherheit in Flensburg.',
    codeForGermanyUrl: 'https://codefor.de/projekte/fl-open-accident-map/',
    websiteUrl: 'https://unfallkarte.oklabflensburg.de',
    githubUrl: 'https://github.com/oklabflensburg/open-accident-map',
    dataSourceUrl: 'https://unfallatlas.statistikportal.de',
    thumbnail: '/open-data/projects/unfallkarte.webp',
    thumbnailSourceUrl: 'https://codefor.de/projects/flensburg/screenshot_unfallkarte.jpg'
  }
]

export const okLabProjectCategories = [...new Set(okLabProjects.map(project => project.category))]
  .sort((first, second) => first.localeCompare(second, 'de'))

export function filterOKLabProjects(projects: OKLabProject[], search: string, category: string) {
  const term = search.trim().toLocaleLowerCase('de')

  return projects.filter((project) => {
    const matchesCategory = !category || project.category === category
    const searchable = `${project.title} ${project.description} ${project.category}`.toLocaleLowerCase('de')
    return matchesCategory && (!term || searchable.includes(term))
  })
}
