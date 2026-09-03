import type { DocumentationPage } from '~/types/documentation'
import { projectConfig } from '~/config/project'

export const documentationPages: DocumentationPage[] = [
  {
    slug: '', title: 'Stadtplaner-Dokumentation', navTitle: 'Übersicht',
    description: 'Benutzerhandbuch für Karte, Flächen, OpenStreetMap, Benachrichtigungen und Benutzerkonten.',
    group: 'Einstieg', keywords: ['Hilfe', 'Handbuch', 'Stadtplaner'], audience: 'public',
    sections: [{ id: 'ueberblick', title: 'Überblick', blocks: [
      { type: 'paragraph', text: 'Der schlanke Stadtplaner-Host stellt eine interaktive Karte, generische Polygone, Konten, Berechtigungen, Benachrichtigungen und offene Modulschnittstellen bereit.' },
      { type: 'links', items: [{ label: 'Erste Schritte', to: '/dokumentation/erste-schritte' }, { label: 'Karte bedienen', to: '/dokumentation/karte' }, { label: 'Flächen verstehen', to: '/dokumentation/flaechen' }] }
    ] }, { id: 'quellcode-und-entwicklung', title: 'Quellcode und Entwicklung', blocks: [
      { type: 'links', items: [{ label: 'Offizielles GitHub-Repository', to: projectConfig.github.url, provider: 'github' }] }
    ] }]
  },
  {
    slug: 'erste-schritte', title: 'Erste Schritte', navTitle: 'Erste Schritte',
    description: 'Von der Karte zur Detailansicht einer Fläche.', group: 'Einstieg',
    keywords: ['Start', 'Navigation'], audience: 'public', sections: [
      { id: 'karte-oeffnen', title: 'Karte öffnen', blocks: [{ type: 'steps', items: [{ title: 'Ausschnitt wählen', text: 'Verschieben und zoomen Sie die Karte.' }, { title: 'Fläche auswählen', text: 'Wählen Sie ein Polygon oder OSM-Objekt aus.' }, { title: 'Details öffnen', text: 'Folgen Sie bei Polygonen dem Link zur Detailseite.' }] }] }
    ]
  },
  {
    slug: 'karte', title: 'Karte bedienen', navTitle: 'Karte', description: 'Kartennavigation, Auswahl und Ebenen.',
    group: 'Karte und Daten', keywords: ['Karte', 'MapLibre', 'Zoom', 'POI', 'Deep Link'], audience: 'public', sections: [
      { id: 'navigation', title: 'Navigation', blocks: [{ type: 'paragraph', text: 'Die Karte lässt sich mit Maus, Tastatur und Touch-Gesten bedienen. Die öffentliche Übersicht bleibt schreibgeschützt.' }] },
      { id: 'auswahl', title: 'Auswahl', blocks: [{ type: 'paragraph', text: 'Ausgewählte Polygone, OSM-Objekte und Modulobjekte erscheinen in derselben generischen Auswahloberfläche.' }] },
      { id: 'poi-deep-links', title: 'POI-Deep-Links', blocks: [
        { type: 'paragraph', text: 'Der Parameter poi grenzt die Karte auf eine semantische Kategorie für Orte und Einrichtungen ein. Ein Link wie /karte?poi=cafe aktiviert den Café-Filter auch nach einem Neuladen. Die konkrete Datenquelle ist nicht Teil dieses öffentlichen Vertrags.' },
        { type: 'code', language: 'text', code: '/karte?poi=cafe\n/karte?poi=restaurant' }
      ] }
    ]
  },
  {
    slug: 'filter', title: 'Filter', navTitle: 'Filter', description: 'Sichtbare Kartendaten eingrenzen.',
    group: 'Karte und Daten', keywords: ['Filter', 'Branche', 'Etage'], audience: 'public', sections: [
      { id: 'verwenden', title: 'Filter verwenden', blocks: [{ type: 'paragraph', text: 'Filter grenzen generische Polygone und passende lokale OpenStreetMap-Objekte ein. Fehlende Werte werden nicht geraten.' }] }
    ]
  },
  {
    slug: 'openstreetmap', title: 'OpenStreetMap', navTitle: 'OpenStreetMap', description: 'Lokale OSM-Snapshots und Quellenhinweise.',
    group: 'Karte und Daten', keywords: ['OpenStreetMap', 'OSM', 'Gebäude', 'lokale Datenbank'], audience: 'public', sections: [
      { id: 'lokale-daten', title: 'Lokale Daten', blocks: [{ type: 'paragraph', text: 'Die Karte liest neutrale OSM-Objektsnapshots aus der lokalen Datenbank. OSM-Daten bleiben schreibgeschützt und behalten ihre Herkunft.' }] },
      { id: 'osm-daten-ergaenzen', title: 'OSM-Daten ergänzen', blocks: [{ type: 'paragraph', text: 'Änderungen an OpenStreetMap erfolgen in den dafür vorgesehenen OSM-Werkzeugen.' }] }
    ]
  },
  {
    slug: 'flaechen', title: 'Flächen', navTitle: 'Flächen', description: 'Generische Polygone und öffentliche Details.',
    group: 'Karte und Daten', keywords: ['Polygon', 'Fläche', 'Geometrie', 'Leerstand'], audience: 'public', sections: [
      { id: 'polygon', title: 'Was ist eine Fläche?', blocks: [{ type: 'paragraph', text: 'Eine Fläche ist ein eigenständig gepflegtes Polygon mit öffentlichen und berechtigungsgeschützten Attributen.' }] },
      { id: 'leerstand', title: 'Statusangaben', blocks: [{ type: 'paragraph', text: 'Ein unbekannter Belegungsstatus wird nicht als belegt oder leerstehend interpretiert.' }] }
    ]
  },
  {
    slug: 'flaechen-bearbeiten', title: 'Flächen bearbeiten', navTitle: 'Bearbeiten', description: 'Attribute und Geometrie sicher ändern.',
    group: 'Konto und Bearbeitung', keywords: ['Autosave', 'Bearbeiten', 'Geometrie'], audience: 'login', sections: [
      { id: 'autosave', title: 'Automatisches Speichern', blocks: [{ type: 'paragraph', text: 'Berechtigte Änderungen werden per Autosave gespeichert. Konflikte verlangen ein erneutes Laden statt fremde Änderungen zu überschreiben.' }] }
    ]
  },
  {
    slug: 'benutzerkonto', title: 'Benutzerkonto', navTitle: 'Benutzerkonto', description: 'Registrierung, Profil und Kontosicherheit.',
    group: 'Konto und Bearbeitung', keywords: ['Login', 'Profil', 'Passwort', 'MFA'], audience: 'login', sections: [
      { id: 'sicherheit', title: 'Kontosicherheit', blocks: [{ type: 'paragraph', text: 'E-Mail-Bestätigung, sichere Sitzungen und optionale Mehrfaktor-Authentisierung schützen das Konto.' }] }
    ]
  },
  {
    slug: 'benachrichtigungen', title: 'Benachrichtigungen', navTitle: 'Benachrichtigungen', description: 'Hinweise lesen und Ressourcen folgen.',
    group: 'Konto und Bearbeitung', keywords: ['Benachrichtigung', 'Ungelesen', 'Folgen'], audience: 'login', sections: [
      { id: 'verwenden', title: 'Benachrichtigungen verwenden', blocks: [{ type: 'paragraph', text: 'Angemeldete Personen können Benachrichtigungen auflisten, als gelesen markieren, Präferenzen ändern und generischen Ressourcen folgen.' }] }
    ]
  },
  {
    slug: 'rollen', title: 'Rollen und Berechtigungen', navTitle: 'Rollen', description: 'Zugriffe und Verwaltungsrechte.',
    group: 'Konto und Bearbeitung', keywords: ['Rolle', 'Berechtigung'], audience: 'verwaltung', sections: [
      { id: 'serverseitig', title: 'Serverseitige Prüfung', blocks: [{ type: 'paragraph', text: 'Das Backend erzwingt Berechtigungen unabhängig von sichtbaren Bedienelementen.' }] }
    ]
  },
  {
    slug: 'administration', title: 'Administration', navTitle: 'Administration', description: 'Generische Host-Verwaltung.',
    group: 'Hilfe', keywords: ['Administration', 'Module', 'Cache'], audience: 'superuser', sections: [
      { id: 'module', title: 'Module verwalten', blocks: [{ type: 'paragraph', text: 'Die Betriebsansicht zeigt installierte Module, deren Status und generische Host-Diagnosen.' }] }
    ]
  },
  {
    slug: 'api', title: 'Öffentliche API', navTitle: 'API', description: 'OpenAPI und generische Host-Endpunkte.',
    group: 'Quellcode und Entwicklung', keywords: ['API', 'OpenAPI', 'Module'], audience: 'public', sections: [
      { id: 'quellcode', title: 'Verträge und Quellcode', blocks: [{ type: 'paragraph', text: 'Der Host veröffentlicht Auth-, Polygon-, Benachrichtigungs- und Modulschnittstellen. Fachmodule ergänzen eigene Routen.' }, { type: 'links', items: [{ label: 'Quellcode', to: projectConfig.github.url, provider: 'github' }] }] }
    ]
  }
]

export const documentationGroupOrder = [
  'Einstieg', 'Karte und Daten', 'Konto und Bearbeitung', 'Hilfe', 'Quellcode und Entwicklung'
] as const

export const documentationPaths = documentationPages.map(page => page.slug ? `/dokumentation/${page.slug}` : '/dokumentation')
