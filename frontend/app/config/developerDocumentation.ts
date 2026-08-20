import type { DocumentationPage } from '~/types/documentation'
import { projectConfig } from '~/config/project'

const repo = projectConfig.github.url
const doc = (path: string) => `${repo}/blob/main/${path}`

export const developerDocumentationPages: DocumentationPage[] = [
  {
    slug: '',
    title: 'Entwicklerdokumentation',
    navTitle: 'Übersicht',
    description: 'Technischer Einstieg in Architektur, APIs, GIS-Daten, Suche, Tests und Betrieb des Open City Planner.',
    group: 'Entwicklung',
    keywords: ['Entwickler', 'Architektur', 'Open Source', 'Nuxt', 'FastAPI', 'PostGIS'],
    audience: 'public',
    sections: [
      {
        id: 'architektur',
        title: 'Technischer Überblick',
        blocks: [
          { type: 'paragraph', text: 'Der Open City Planner besteht aus einem Nuxt-Frontend, einem FastAPI-Backend und PostgreSQL/PostGIS als fachlicher Datenbank. Redis kann öffentliche Lesezugriffe cachen. OpenStreetMap-, Statistik- und Stadtplaner-Daten werden über klar getrennte Services und öffentliche API-Verträge zusammengeführt.' },
          { type: 'links', items: [
            { label: 'Architektur', to: '/dokumentation/entwickler/architektur', description: 'Frontend, Backend, Datenbank und Datenflüsse.' },
            { label: 'API', to: '/dokumentation/entwickler/api', description: 'Öffentliche Ressourcen und OpenAPI.' },
            { label: 'OpenStreetMap', to: '/dokumentation/entwickler/osm', description: 'Import, Mapping, Gebäude, POIs und Synchronisation.' },
            { label: 'Kommunale Statistik', to: '/dokumentation/entwickler/statistik', description: 'Import, Gebietsbezug und Zeitreihen.' },
            { label: 'Intelligente Suche', to: '/dokumentation/entwickler/assistant', description: 'SearchPlan, Assistant, Groq und read-only Tools.' },
            { label: 'CI und Tests', to: '/dokumentation/entwickler/ci', description: 'Qualitätschecks und E2E-Tests.' },
            { label: 'Deployment und Betrieb', to: '/dokumentation/entwickler/deployment', description: 'Produktionsbetrieb und zentrale Betriebsreferenz.' }
          ] }
        ]
      },
      {
        id: 'source-of-truth',
        title: 'Technische Source of Truth',
        blocks: [
          { type: 'paragraph', text: 'Diese Website bietet einen kuratierten technischen Einstieg. Implementierungsnahe Spezialfälle, Performance-Analysen, SQL-Explain-Artefakte und ausführliche Betriebsanleitungen bleiben im Repository unter docs/ die vollständige technische Referenz.' },
          { type: 'links', items: [
            { label: 'Repository', to: repo, description: 'Quellcode des Open City Planner.', provider: 'github' },
            { label: 'Technische Dokumente', to: `${repo}/tree/main/docs`, description: 'Vollständige Referenz unter docs/.', provider: 'github' },
            { label: 'Beitragen', to: projectConfig.github.contributingUrl, description: 'Contribution-Workflow und lokale Qualitätschecks.', provider: 'github' }
          ] }
        ]
      }
    ]
  },
  {
    slug: 'architektur',
    title: 'Architektur',
    navTitle: 'Architektur',
    description: 'Aufbau des Open City Planner und Trennung von Frontend, Backend, Language Plane und GIS Data Plane.',
    group: 'Entwicklung',
    keywords: ['Architektur', 'Nuxt', 'FastAPI', 'PostGIS', 'Redis', 'MapLibre'],
    audience: 'public',
    sections: [
      { id: 'komponenten', title: 'Kernkomponenten', blocks: [
        { type: 'table', headers: ['Komponente', 'Aufgabe'], rows: [
          ['Nuxt-Frontend', 'Karte, Filter, Analyse, Dokumentation und Assistant-Oberfläche'],
          ['FastAPI-Backend', 'Öffentliche API, Authentifizierung, Fachservices, Imports und Assistant-Orchestrierung'],
          ['PostgreSQL/PostGIS', 'Fachliche Hauptdatenbank und räumliche Abfragen'],
          ['MapLibre', 'Interaktive GIS-Darstellung im Browser'],
          ['Redis', 'Optionaler Read-Cache; nicht fachliche Source of Truth']
        ] },
        { type: 'links', items: [
          { label: 'Frontend Design', to: doc('docs/frontend-design.md'), provider: 'github' },
          { label: 'Map Layer Order', to: doc('docs/map-layer-order.md'), provider: 'github' },
          { label: 'Map Performance', to: doc('docs/map-performance.md'), provider: 'github' }
        ] }
      ] },
      { id: 'datenfluss', title: 'Daten- und Sprachschicht', blocks: [
        { type: 'paragraph', text: 'GIS-Ergebnisse werden in PostGIS und den vorhandenen Stadtplaner-Services erzeugt. Das Sprachmodell ist keine Datenquelle und erhält keinen freien SQL-Zugriff. Große GeoJSON-Ergebnisse sollen direkt vom Backend an die Karte gelangen und nicht durch das Sprachmodell geleitet werden.' }
      ] }
    ]
  },
  {
    slug: 'api',
    title: 'API und Backend',
    navTitle: 'API',
    description: 'FastAPI, OpenAPI und die wichtigsten öffentlichen Ressourcen des Stadtplaners.',
    group: 'Entwicklung',
    keywords: ['API', 'FastAPI', 'OpenAPI', 'ReDoc', 'REST'],
    audience: 'public',
    sections: [
      { id: 'ressourcen', title: 'Öffentliche Ressourcen', blocks: [
        { type: 'list', items: ['Analysegebiete und GeoJSON', 'Analytics und Gebietsvergleiche', 'Kommunale Statistik und Zeitreihen', 'Öffentliche Stadtplaner-Flächen', 'OpenStreetMap-Features und Details', 'Read-only Assistant und intelligente Suche'] },
        { type: 'paragraph', text: 'Die aktuelle OpenAPI des laufenden Backends ist die maßgebliche Endpoint-Referenz. Entwicklerdokumentation sollte deshalb fachliche Ressourcen erklären, aber keine zweite vollständige manuell gepflegte Endpoint-Liste erzeugen.' }
      ] },
      { id: 'sicherheit', title: 'Sicherheitsgrenzen', blocks: [
        { type: 'paragraph', text: 'Öffentliche Assistant-Funktionen sind read-only. Admin-, Auth-, User- und schreibende Fachoperationen gehören nicht zur Tool-Allowlist des Sprachassistenten.' }
      ] }
    ]
  },
  {
    slug: 'osm',
    title: 'OpenStreetMap und GIS-Daten',
    navTitle: 'OpenStreetMap',
    description: 'Lokale OSM-Daten, Gebäude, POIs, kanonische Kategorien und Synchronisation.',
    group: 'Daten',
    keywords: ['OSM', 'OpenStreetMap', 'Gebäude', 'Building', 'POI', 'Sync', 'PostGIS'],
    audience: 'public',
    sections: [
      { id: 'modell', title: 'Lokale OSM-Daten', blocks: [
        { type: 'paragraph', text: 'OpenStreetMap-Daten werden lokal für die GIS-Abfragen des Stadtplaners verwendet. Fachliche Geschäftsfilter und OSM-Feature-Kategorien wie Gebäude sind getrennte Taxonomien und dürfen nicht miteinander vermischt werden.' },
        { type: 'links', items: [
          { label: 'OSM-Datenmodell und Mapping', to: doc('docs/osm-data.md'), provider: 'github' },
          { label: 'Stündliche OSM-Synchronisation', to: doc('docs/osm-hourly-sync.md'), provider: 'github' }
        ] }
      ] },
      { id: 'geometrie', title: 'Räumliche Abfragen', blocks: [
        { type: 'paragraph', text: 'PostGIS bleibt die Suchmaschine für Geometrien, Gebietszuordnung, BBOX-Vorfilter, Entfernungen und exakte räumliche Einschränkungen. Ein Sprachmodell interpretiert die Anfrage, berechnet aber keine GIS-Geometrien.' }
      ] }
    ]
  },
  {
    slug: 'statistik',
    title: 'Kommunale Statistik',
    navTitle: 'Statistik',
    description: 'Technischer Überblick über Statistikimport, Kennzahlen, Zeitreihen und Gebietsvererbung.',
    group: 'Daten',
    keywords: ['Statistik', 'Bevölkerung', 'metric_key', 'Zeitreihe', 'Import'],
    audience: 'public',
    sections: [
      { id: 'datenmodell', title: 'Statistikmodell', blocks: [
        { type: 'paragraph', text: 'Kommunale Statistik wird getrennt von den aus Stadtplaner- und OSM-Daten berechneten Analytics geführt. Die API stellt Gebietsstatistiken und Kennzahl-Zeitreihen bereit und trägt Quelle, Periode und gegebenenfalls die Vererbung eines Werts vom übergeordneten Gebiet.' },
        { type: 'links', items: [{ label: 'Vollständige Statistik-Referenz', to: doc('docs/flensburg-statistics.md'), provider: 'github' }] }
      ] }
    ]
  },
  {
    slug: 'assistant',
    title: 'Intelligente Suche und Assistant',
    navTitle: 'Suche & Assistant',
    description: 'SearchPlan, deterministischer Fast Path, Groq, Tool Registry und kontrollierte Knowledge-Abfragen.',
    group: 'Entwicklung',
    keywords: ['Assistant', 'Groq', 'LLM', 'SearchPlan', 'Tool Registry', 'Knowledge'],
    audience: 'public',
    sections: [
      { id: 'pipeline', title: 'Verarbeitung', blocks: [
        { type: 'steps', items: [
          { title: 'Eindeutige Kommandos', text: 'Ein kleiner deterministischer Fast Path verarbeitet triviale und sichere Karten- oder Filterbefehle ohne Modellaufruf.' },
          { title: 'Sprachinterpretation', text: 'Komplexere Formulierungen können über den konfigurierten LLM-Provider in einen validierten Plan übersetzt werden.' },
          { title: 'Read-only Tools', text: 'Nur explizit freigegebene, Pydantic-validierte Werkzeuge dürfen vorhandene Stadtplaner-Services aufrufen.' },
          { title: 'Fachliche Antwort', text: 'Zahlen und GIS-Ergebnisse stammen aus PostGIS und den Fachservices; Knowledge liefert kontrollierte Erklärungen.' }
        ] },
        { type: 'links', items: [
          { label: 'Intelligente Suche', to: doc('docs/intelligent-search.md'), provider: 'github' },
          { label: 'Stadtplaner Assistant', to: doc('docs/stadtplaner-assistant.md'), provider: 'github' }
        ] }
      ] },
      { id: 'groq', title: 'Groq', blocks: [
        { type: 'paragraph', text: 'Groq ist eine austauschbare Sprach- und Orchestrierungsschicht. API-Schlüssel bleiben ausschließlich im Backend. Das Modell erhält keinen direkten Datenbankzugang und keine vollständige OpenAPI als frei ausführbare Tool-Liste.' }
      ] }
    ]
  },
  {
    slug: 'ci',
    title: 'CI und Tests',
    navTitle: 'CI & Tests',
    description: 'Backend-, Frontend-, Migrations- und Browser-Tests in GitHub Actions.',
    group: 'Qualität',
    keywords: ['CI', 'Tests', 'GitHub Actions', 'pytest', 'Vitest', 'Playwright'],
    audience: 'public',
    sections: [
      { id: 'checks', title: 'Qualitätssicherung', blocks: [
        { type: 'paragraph', text: 'GitHub Actions prüft Backend, Frontend, Migrationen und zentrale Nutzerwege. Die vollständigen und jeweils aktuellen Jobnamen, lokalen Befehle und Branch-Protection-Empfehlungen stehen in der technischen CI-Referenz.' },
        { type: 'links', items: [{ label: 'CI-Referenz', to: doc('docs/ci.md'), provider: 'github' }] }
      ] }
    ]
  },
  {
    slug: 'deployment',
    title: 'Deployment und Betrieb',
    navTitle: 'Deployment',
    description: 'Produktionsbetrieb von Frontend, Backend, PostGIS, Redis, Imports, Assistant und systemd-Workern.',
    group: 'Betrieb',
    keywords: ['Deployment', 'Produktion', 'systemd', 'Nginx', 'PostGIS', 'Redis', 'Backup'],
    audience: 'public',
    sections: [
      { id: 'prinzip', title: 'Betriebsprinzip', blocks: [
        { type: 'paragraph', text: 'Die Entwicklerseite bietet den Betriebsüberblick. Konkrete Installations-, Update-, Backup-, Worker- und Diagnosebefehle werden zentral in docs/deployment.md gepflegt, damit README und öffentliche Hilfeseiten nicht zu Betriebshandbüchern anwachsen.' },
        { type: 'links', items: [{ label: 'Deployment-Referenz', to: doc('docs/deployment.md'), provider: 'github' }] }
      ] },
      { id: 'checkliste', title: 'Vor einem produktiven Update', blocks: [
        { type: 'list', items: ['Aktuellen Branch und CI-Status prüfen.', 'Vor Schemaänderungen ein Datenbank-Backup sicherstellen.', 'Alembic-Migrationen und Frontend-Build ausführen.', 'Services und Timer nach dem Update prüfen.', 'Read-only Smoke Tests für API, Karte, Statistik und Assistant durchführen.', 'Logs nach dem Restart kontrollieren.'] }
      ] }
    ]
  }
]

export function findDeveloperDocumentationPage(slug: string | undefined) {
  return developerDocumentationPages.find(page => page.slug === (slug || ''))
}
