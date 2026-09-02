import type { DocumentationPage } from '~/types/documentation'
import { projectConfig } from '~/config/project'

const repo = projectConfig.github.url
const doc = (path: string) => `${repo}/blob/main/${path}`

export const developerDocumentationPages: DocumentationPage[] = [
  {
    slug: '',
    title: 'Entwicklerdokumentation',
    navTitle: 'Übersicht',
    description: 'Technischer Einstieg in Architektur, APIs, GIS-Daten, Module, Tests und Betrieb des Open City Planner.',
    group: 'Entwicklung',
    keywords: ['Entwickler', 'Architektur', 'Open Source', 'Nuxt', 'FastAPI', 'PostGIS'],
    audience: 'public',
    sections: [
      {
        id: 'architektur',
        title: 'Technischer Überblick',
        blocks: [
          { type: 'paragraph', text: 'Der Open City Planner besteht aus einem schlanken Nuxt-/FastAPI-Host und PostgreSQL/PostGIS. Redis kann öffentliche Lesezugriffe cachen. Fachfunktionen werden über stabile Modulverträge ergänzt.' },
          { type: 'links', items: [
            { label: 'Architektur', to: '/dokumentation/entwickler/architektur', description: 'Frontend, Backend, Datenbank und Datenflüsse.' },
            { label: 'API', to: '/dokumentation/entwickler/api', description: 'Öffentliche Ressourcen und OpenAPI.' },
            { label: 'OpenStreetMap', to: '/dokumentation/entwickler/osm', description: 'Import, Mapping, Gebäude, POIs und Synchronisation.' },
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
          ['Nuxt-Frontend', 'Karte, Filter, Auswahl, Modulbeiträge und Dokumentation'],
          ['FastAPI-Backend', 'Öffentliche API, Authentifizierung, Fachservices und Imports'],
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
      { id: 'datenfluss', title: 'Datenfluss', blocks: [
        { type: 'paragraph', text: 'GIS-Ergebnisse werden in PostGIS und den vorhandenen Stadtplaner-Services erzeugt. Große GeoJSON-Ergebnisse gelangen direkt vom Backend an die Karte.' }
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
        { type: 'list', items: ['Authentifizierung und Berechtigungen', 'Öffentliche Polygone', 'Benachrichtigungen', 'Modulbeiträge', 'Lokale OpenStreetMap-Snapshots'] },
        { type: 'paragraph', text: 'Die aktuelle OpenAPI des laufenden Backends ist die maßgebliche Endpoint-Referenz. Entwicklerdokumentation sollte deshalb fachliche Ressourcen erklären, aber keine zweite vollständige manuell gepflegte Endpoint-Liste erzeugen.' }
      ] },
      { id: 'sicherheit', title: 'Sicherheitsgrenzen', blocks: [
        { type: 'paragraph', text: 'Admin-, Auth-, User- und schreibende Fachoperationen sind serverseitig geschützt und von öffentlichen Lese-Endpunkten getrennt.' }
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
        { type: 'paragraph', text: 'PostGIS bleibt die Suchmaschine für Geometrien, BBOX-Vorfilter, Entfernungen und exakte räumliche Einschränkungen.' }
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
    description: 'Produktionsbetrieb von Frontend, Backend, PostGIS, Redis, Modulen und systemd-Workern.',
    group: 'Betrieb',
    keywords: ['Deployment', 'Produktion', 'systemd', 'Nginx', 'PostGIS', 'Redis', 'Backup'],
    audience: 'public',
    sections: [
      { id: 'prinzip', title: 'Betriebsprinzip', blocks: [
        { type: 'paragraph', text: 'Die Entwicklerseite bietet den Betriebsüberblick. Konkrete Installations-, Update-, Backup-, Worker- und Diagnosebefehle werden zentral in docs/deployment.md gepflegt, damit README und öffentliche Hilfeseiten nicht zu Betriebshandbüchern anwachsen.' },
        { type: 'links', items: [{ label: 'Deployment-Referenz', to: doc('docs/deployment.md'), provider: 'github' }] }
      ] },
      { id: 'checkliste', title: 'Vor einem produktiven Update', blocks: [
        { type: 'list', items: ['Aktuellen Branch und CI-Status prüfen.', 'Vor Schemaänderungen ein Datenbank-Backup sicherstellen.', 'Alembic-Migrationen und Frontend-Build ausführen.', 'Services und Timer nach dem Update prüfen.', 'Read-only Smoke Tests für API, Karte, Benachrichtigungen und installierte Module durchführen.', 'Logs nach dem Restart kontrollieren.'] }
      ] }
    ]
  }
]

export function findDeveloperDocumentationPage(slug: string | undefined) {
  return developerDocumentationPages.find(page => page.slug === (slug || ''))
}
