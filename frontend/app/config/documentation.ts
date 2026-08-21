import type { DocumentationPage } from '~/types/documentation'
import { projectConfig } from '~/config/project'

export const documentationPages: DocumentationPage[] = [
  {
    slug: '',
    title: 'Stadtplaner-Dokumentation',
    navTitle: 'Übersicht',
    description: 'Benutzerhandbuch für Karte, Suche, Daten, Analysen, Flächen und Benutzerkonto des Stadtplaners.',
    group: 'Einstieg',
    keywords: ['Hilfe', 'Handbuch', 'Anleitung', 'Stadtplaner', 'Suche', 'Statistik', 'OSM'],
    audience: 'public',
    sections: [
      {
        id: 'was-ist-der-stadtplaner',
        title: 'Was ist der Stadtplaner?',
        blocks: [
          { type: 'paragraph', text: 'Der Stadtplaner macht Verkaufsflächen und ausgewählte Stadtkennzahlen für Flensburg auf einer interaktiven Karte zugänglich. Öffentliche Informationen können ohne Anmeldung angesehen werden.' },
          { type: 'callout', variant: 'info', title: 'Daten mit unterschiedlicher Herkunft', text: 'Flächendaten, manuell gepflegte Kennzahlen und ergänzende OpenStreetMap-Informationen haben jeweils eine eigene Quelle. Die Detailansichten kennzeichnen diese Zusammenhänge.' }
        ]
      },
      {
        id: 'passenden-einstieg-waehlen',
        title: 'Passenden Einstieg wählen',
        blocks: [
          { type: 'steps', items: [{ title: 'Karte öffnen', text: 'Öffnen Sie die öffentliche Kartenübersicht.' }, { title: 'Fläche auswählen', text: 'Klicken oder tippen Sie auf ein farbig umrandetes Polygon.' }, { title: 'Detailseite öffnen', text: 'Folgen Sie dem Link in der Flächenvorschau.' }, { title: 'Bei Berechtigung bearbeiten', text: 'Änderungen erfolgen ausschließlich auf der Detailseite und werden dort automatisch gespeichert.' }] },
          {
            type: 'links',
            items: [
              { label: 'Karte öffnen', to: '/', description: 'Direkt zur interaktiven Kartenübersicht.' },
              { label: 'Erste Schritte', to: '/dokumentation/erste-schritte', description: 'Die wichtigsten Bedienwege in wenigen Minuten kennenlernen.' },
              { label: 'Intelligente Suche', to: '/dokumentation/suche', description: 'Kartenbefehle und Fragen in Alltagssprache verwenden.' },
              { label: 'Karte bedienen', to: '/dokumentation/karte', description: 'Navigieren, Flächen auswählen und Ebenen bedienen.' },
              { label: 'Kommunale Statistik', to: '/dokumentation/statistik', description: 'Werte, Zeitreihen, Quellen und übergeordnete Statistikgebiete verstehen.' },
              { label: 'Datenquellen und Aktualität', to: '/dokumentation/datenquellen', description: 'Stadtplaner, OpenStreetMap und kommunale Statistik unterscheiden.' },
              { label: 'Flächen bearbeiten', to: '/dokumentation/flaechen-bearbeiten', description: 'Attribute und Geometrie mit Autosave ändern.' },
              { label: 'Verwaltung', to: '/dokumentation/verwaltung', description: 'Nicht öffentliche Felder und Kennzahlen verwalten.' }
            ]
          }
        ]
      },
      {
        id: 'zugaenge-und-rollen',
        title: 'Zugänge und Rollen',
        blocks: [
          { type: 'table', headers: ['Bereich', 'Zugang'], rows: [['Karte, Flächendetails und Dokumentation', 'Öffentlich'], ['Profil und eigene Flächen', 'Angemeldetes Konto'], ['Freigegebene Flächen bearbeiten', 'Verifiziertes, berechtigtes Konto'], ['Interne Verwaltungsfelder und Kennzahlen', 'Rolle VERWALTUNG']] },
          { type: 'links', items: [{ label: 'Rollen und Berechtigungen im Detail', to: '/dokumentation/rollen' }] }
        ]
      },
      {
        id: 'quellcode-und-entwicklung',
        title: 'Quellcode und Entwicklung',
        blocks: [
          { type: 'paragraph', text: 'Stadtplaner wird als Open-Source-Projekt entwickelt. Das offizielle GitHub-Repository enthält den Quellcode für Frontend und Backend sowie die technische Dokumentation für Entwicklung und Betrieb.' },
          { type: 'links', items: [{ label: 'Offizielles GitHub-Repository', to: projectConfig.github.url, description: 'Quellcode und technische Projektdokumentation öffnen.', provider: 'github' }, { label: 'Zum Projekt beitragen', to: projectConfig.github.contributingUrl, description: 'Lokales Setup, Qualitätsanforderungen und Pull-Request-Ablauf.', provider: 'github' }] }
        ]
      }
    ]
  },
  {
    slug: 'erste-schritte',
    title: 'Erste Schritte',
    navTitle: 'Erste Schritte',
    description: 'Vom Öffnen der Karte bis zur Detailansicht einer Fläche.',
    group: 'Einstieg',
    keywords: ['Start', 'Einführung', 'Workflow', 'Navigation'],
    audience: 'public',
    sections: [
      {
        id: 'karte-erkunden',
        title: 'Karte erkunden',
        blocks: [
          { type: 'steps', items: [{ title: 'Kartenausschnitt wählen', text: 'Verschieben Sie die Karte mit Maus oder Finger und nutzen Sie die Plus- und Minus-Schaltflächen zum Zoomen.' }, { title: 'Fläche auswählen', text: 'Klicken oder tippen Sie auf ein farbig umrandetes Polygon.' }, { title: 'Vorschau prüfen', text: 'Die Karte zeigt die wichtigsten öffentlichen Angaben und lädt verfügbare OSM-Informationen.' }, { title: 'Details öffnen', text: 'Folgen Sie dem Link zur Flächendetailseite, um Beschreibung, Adresse, Geometrie und weitere Angaben zu sehen.' }] },
          { type: 'callout', variant: 'tip', title: 'Auswahl zurücksetzen', text: 'Mit der Zurücksetzen-Schaltfläche an der Karte kehren Sie zum Ausgangsausschnitt zurück.' }
        ]
      },
      {
        id: 'ergebnisse-eingrenzen',
        title: 'Ergebnisse eingrenzen',
        blocks: [
          { type: 'paragraph', text: 'Die Filter für Verkaufsflächengröße, Etage, Branche, Belegungsstatus und Betriebsform wirken gemeinsam auf Stadtplaner-Flächen, passende lokale OpenStreetMap-Objekte, Karte und Auswertungen.' },
          { type: 'links', items: [{ label: 'Filter verstehen', to: '/dokumentation/filter' }, { label: 'Kennzahlen einordnen', to: '/dokumentation/fast-facts' }] }
        ]
      },
      {
        id: 'konto-verwenden',
        title: 'Konto verwenden',
        blocks: [
          { type: 'paragraph', text: 'Für die öffentliche Recherche ist kein Konto erforderlich. Ein Konto wird benötigt, um das eigene Profil und zugeordnete Flächen aufzurufen. Änderungen an Flächen setzen zusätzlich eine bestätigte E-Mail-Adresse und eine Bearbeitungsberechtigung voraus.' },
          { type: 'links', items: [{ label: 'Benutzerkonto', to: '/dokumentation/benutzerkonto' }, { label: 'Rollen und Rechte', to: '/dokumentation/rollen' }] }
        ]
      }
    ]
  },
  {
    slug: 'suche',
    title: 'Intelligente Suche',
    navTitle: 'Intelligente Suche',
    description: 'Mit verständlichen Kartenbefehlen und Fragen nach Gebieten, Flächen, Kennzahlen und Statistik suchen.',
    group: 'Einstieg',
    keywords: ['KI', 'Suche', 'Assistant', 'Assistent', 'natürliche Sprache', 'Kartenbefehl', 'Statistik'],
    audience: 'public',
    sections: [
      {
        id: 'was-die-suche-kann',
        title: 'Was die Suche kann',
        blocks: [
          { type: 'paragraph', text: 'Die intelligente Suche versteht ausgewählte Kartenbefehle und Fragen in Alltagssprache. Sie kann Gebiete auswählen, Kartenobjekte filtern, Kennzahlen anzeigen und Begriffe aus der Projektdokumentation erklären. Die Karte bleibt dabei die Hauptdarstellung.' },
          { type: 'paragraph', text: 'Zahlen und Kartenobjekte stammen aus den vorhandenen Stadtplaner-, OpenStreetMap- und Statistikdaten. Ein optionales Sprachmodell hilft nur beim Verstehen komplexerer Formulierungen und ist nicht selbst die Datenquelle.' }
        ]
      },
      {
        id: 'beispiele',
        title: 'Beispiele für Suchanfragen',
        blocks: [
          { type: 'list', items: ['„Alle Stadtteile anzeigen“', '„Zeige Gastronomieflächen in der Altstadt“', '„Gibt es Flächen größer als 350 qm in Flensburg?“', '„Nur Leerstände“', '„Wie viele POIs gibt es in der Altstadt?“', '„Welche Statistiken gibt es für die Altstadt?“', '„Wie hat sich die Bevölkerung in der Altstadt entwickelt?“', '„Was bedeutet Leerstandsquote?“', '„Zeige Rathaus in Flensburg“'] },
          { type: 'callout', variant: 'info', title: 'Numerische Flächensuche', text: 'Angaben wie „größer als 350 qm“ oder „unter 100 Quadratmeter“ beziehen sich ausschließlich auf die vermessene Polygonfläche gepflegter Stadtplaner-Flächen. OpenStreetMap-Gebäudegrundrisse werden dabei nicht als Verkaufsfläche angenommen.' },
          { type: 'callout', variant: 'tip', title: 'Folgefragen', text: 'Nach einer eindeutigen Gebiets- oder Statistikfrage können kurze Folgefragen wie „Und die Bevölkerung?“ oder „Was bedeutet diese Kennzahl?“ den bisherigen Zusammenhang verwenden.' }
        ]
      },
      {
        id: 'grenzen-und-datenschutz',
        title: 'Grenzen und Datenschutz',
        blocks: [
          { type: 'list', items: ['Nicht jede frei formulierte Frage lässt sich zuverlässig beantworten.', 'Fehlende Werte werden nicht geschätzt, hochgerechnet oder durch null ersetzt.', 'Die Suche liest ausschließlich öffentliche Stadtplaner-Daten und führt keine Änderungen aus.', 'Benutzer-, Verwaltungs- und Anmeldedaten sind nicht Teil der Suchwerkzeuge.', 'Ist die erweiterte Sprachinterpretation nicht verfügbar, funktionieren die bekannten direkten Suchbefehle weiterhin.'] },
          { type: 'links', items: [{ label: 'Datenquellen und Aktualität', to: '/dokumentation/datenquellen' }, { label: 'Häufige Fragen', to: '/dokumentation/faq' }] }
        ]
      }
    ]
  },
  {
    slug: 'karte',
    title: 'Karte bedienen',
    navTitle: 'Karte',
    description: 'Kartennavigation, Flächenauswahl, Vorschau und Kartenebenen.',
    group: 'Karte und Daten',
    keywords: ['MapLibre', 'Zoom', 'Polygon', 'Ebene', 'Reset'],
    audience: 'public',
    sections: [
      {
        id: 'navigieren',
        title: 'Navigieren und zoomen',
        blocks: [
          { type: 'list', items: ['Ziehen Sie die Karte, um den Ausschnitt zu verschieben.', 'Zoomen Sie mit Mausrad, Touch-Geste oder den Plus-/Minus-Schaltflächen.', 'Mit Zurücksetzen stellen Sie den vorgesehenen Ausgangsausschnitt wieder her.', 'Über die Ebenen-Schaltfläche wechseln Sie zwischen angebotenen Kartenansichten.'] },
          { type: 'callout', variant: 'info', title: 'Übersicht ist schreibgeschützt', text: 'Auf der öffentlichen Übersichtskarte können Polygone nur ausgewählt, nicht verschoben oder bearbeitet werden.' }
        ]
      },
      {
        id: 'flaeche-auswaehlen',
        title: 'Fläche auswählen',
        blocks: [
          { type: 'paragraph', text: 'Ein Klick auf ein Polygon markiert die Fläche, passt bei Bedarf den Kartenausschnitt an und öffnet die Analyse- beziehungsweise Vorschauansicht. Dort erscheinen Name, Adresse, Branche, Größe, Etage und Fläche, soweit diese Daten vorhanden sind.' },
          { type: 'paragraph', text: 'Der Link zur Detailseite führt zur dauerhaften Adresse der Fläche. Der Slug dieser Adresse bleibt auch nach späteren Namensänderungen stabil.' }
        ]
      },
      {
        id: 'kategorienfarben',
        title: 'Kategorienfarben',
        blocks: [
          { type: 'paragraph', text: 'Jede gepflegte Branche besitzt eine einheitliche Farbe. Dieselbe Zuordnung erscheint an Kartenpolygonen, Branchenfiltern, Auswertungen und auf der Flächendetailseite. Das ausgeschriebene Kategorienlabel bleibt immer sichtbar; die Farbe dient nur der zusätzlichen Orientierung.' },
          { type: 'callout', variant: 'info', title: 'Unbekannte ältere Kategorie', text: 'Ist ein gespeicherter Kategorienwert nicht in der aktuellen Liste enthalten, bleibt sein Originaltext erhalten und die Oberfläche verwendet eine neutrale Farbe.' }
        ]
      },
      {
        id: 'darstellung-und-performance',
        title: 'Darstellung und Performance',
        blocks: [
          { type: 'paragraph', text: 'Die Karte nutzt WebGL. Viele gleichzeitig geöffnete Karten-Tabs oder knapper Grafikspeicher können dazu führen, dass der Browser den WebGL-Kontext vorübergehend verliert.' },
          { type: 'callout', variant: 'tip', title: 'Wenn die Karte leer bleibt', text: 'Schließen Sie nicht benötigte Karten-Tabs und laden Sie die Seite neu. Die Dokumentationsseiten selbst laden keine interaktive Karte.' }
        ]
      }
    ]
  },
  {
    slug: 'filter',
    title: 'Filter und Kartendarstellung',
    navTitle: 'Filter',
    description: 'Flächen nach Größe, Etage und Branche eingrenzen.',
    group: 'Karte und Daten',
    keywords: ['S', 'M', 'L', 'XL', 'UG', 'EG', 'OG', 'Branche'],
    audience: 'public',
    sections: [
      {
        id: 'verfuegbare-filter',
        title: 'Verfügbare Filter',
        blocks: [
          { type: 'table', headers: ['Filter', 'Mehrfachauswahl'], rows: [['Verkaufsfläche', 'S, M, L und XL frei kombinierbar'], ['Etage', 'UG, EG und OG frei kombinierbar; OG umfasst die gepflegten Ober- und Dachgeschosse'], ['Branchen', 'Eine oder mehrere quellenübergreifende Branchen'], ['Status', 'Belegt, leerstehend oder unbekannt'], ['Betriebsform', 'Filialist, inhabergeführt oder unbekannt'], ['Datenquellen', 'Stadtplaner und OpenStreetMap einzeln ein- oder ausblendbar']] },
          { type: 'paragraph', text: 'Innerhalb einer Filtergruppe gilt ODER, zwischen verschiedenen Gruppen gilt UND. S + M sowie EG + OG bedeutet daher: kleine oder mittlere Fläche und Erd- oder Obergeschoss.' },
          { type: 'paragraph', text: 'Keine Auswahl bedeutet ungefiltert. Jede Gruppe bietet „Alle auswählen“ und „Auswahl aufheben“; „Filter zurücksetzen“ leert alle fachlichen Filter gemeinsam. Der Zustand wird in der URL gespeichert und kann geteilt sowie mit Vor/Zurück wiederhergestellt werden.' }
        ]
      },
      {
        id: 'wirkung-auf-auswertung',
        title: 'Wirkung auf Karte und Auswertung',
        blocks: [
          { type: 'paragraph', text: 'Aktive Filter bestimmen, welche Stadtplaner-Flächen und fachlich passenden OpenStreetMap-Geschäftsobjekte auf der Karte erscheinen. Kontext-POIs wie ÖPNV, Parken oder Kultur bleiben davon getrennt als Umfeld sichtbar. Manuell gepflegte Zentralitäts- und Kaufkraftwerte bleiben eigenständige Referenzwerte.' },
          { type: 'callout', variant: 'info', title: 'Größenklassen', text: 'S, M, L und XL sind derzeit fachlich gepflegte Klassen. Es existiert keine automatische Einteilung anhand zentral festgelegter Quadratmetergrenzen; deshalb werden keine erfundenen Grenzwerte angezeigt.' },
          { type: 'callout', variant: 'important', title: 'Grenzen der OSM-Filterung', text: 'Nicht jedes OpenStreetMap-Objekt enthält Angaben zu Etage, Flächengröße oder Leerstand. Fehlt ein Wert, wird er nicht als Erdgeschoss, belegt oder als bestimmte Größenklasse angenommen. Eine kartierte Gebäude- oder Polygonfläche ist keine behauptete Verkaufsfläche.' },
          { type: 'paragraph', text: 'Die Branchenzahlen berücksichtigen Stadtplaner und passende OSM-Objekte. Sie wenden alle anderen aktiven Filter an, lassen den Branchenfilter selbst aber bewusst außen vor. Ein Tooltip trennt die Counts nach Quelle.' },
          { type: 'callout', variant: 'info', title: 'Keine Treffer', text: 'Eine leere Karte kann eine gültige Filterkombination ohne passende Flächen bedeuten. Ändern Sie einen Filter oder aktivieren Sie weitere Branchen.' }
        ]
      }
    ]
  },
  {
    slug: 'openstreetmap',
    title: 'OpenStreetMap im Stadtplaner',
    navTitle: 'OpenStreetMap',
    description: 'Herkunft, Anzeige und Grenzen der ergänzenden OSM-Daten.',
    group: 'Karte und Daten',
    keywords: ['OSM', 'OpenStreetMap', 'Gebäude', 'lokale Daten', 'Tags', 'POI', 'Datenquelle', 'Aktualität'],
    audience: 'public',
    sections: [
      {
        id: 'herkunft',
        title: 'Woher kommen die Angaben?',
        blocks: [
          { type: 'paragraph', text: 'Der Stadtplaner lädt relevante Punkte und Flächen für den sichtbaren Kartenausschnitt aus der lokalen OpenStreetMap-Datenbank. Beim Verschieben oder Zoomen wird nur der neue Ausschnitt nachgeladen.' },
          { type: 'callout', variant: 'info', title: 'Keine externen Kartenabfragen', text: 'Der Viewport-Layer greift ausschließlich auf lokales PostGIS zu. Der optionale serverseitige Overpass-Rückfall gilt nur für den gesonderten Objektabgleich einer Stadtplaner-Fläche.' }
        ]
      },
      {
        id: 'anzeige',
        title: 'Was wird angezeigt?',
        blocks: [
          { type: 'paragraph', text: 'Farbige POIs und dezente Flächenobjekte werden zoomabhängig dargestellt. Punkte werden bei kleinerem Maßstab gruppiert. Gebäude können separat aktiviert werden und erscheinen ab Zoom 17.' },
          { type: 'paragraph', text: 'Geschäftsbezogene OSM-Tags werden serverseitig auf dieselben Branchen wie Stadtplaner-Flächen abgebildet. Explizites level=-1 wird UG, level=0 EG und ein positives level OG. building:levels wird dabei bewusst nicht als Lage eines Geschäfts verwendet. Leerstand wird nur aus belastbaren Lifecycle-Tags wie shop=vacant oder disused:shop=* abgeleitet.' },
          { type: 'paragraph', text: 'Ist ein OSM-Objekt bereits mit einer Stadtplaner-Fläche verknüpft, hat die gepflegte Stadtplaner-Fläche Vorrang und das OSM-Objekt wird bei aktiven beiden Quellen nicht doppelt dargestellt oder gezählt.' },
          { type: 'paragraph', text: 'Ein Klick zeigt sofort eine Vorschau; zusätzliche Sachdaten werden erst für das ausgewählte Objekt geladen. Im Analysebereich stehen die Kategorienzahlen des aktuellen Kartenausschnitts.' },
          { type: 'list', items: ['Name und OSM-Kategorie, zum Beispiel shop oder amenity', 'Marke und Betreiber', 'Öffnungszeiten und OpenStreetMap-Adresse', 'Auf der Detailseite gegebenenfalls Telefon, E-Mail, Ebene und Gebäudeebenen', 'Sicher verlinkte Website und Link zum Objekt auf OpenStreetMap'] },
          { type: 'paragraph', text: 'OSM-Daten sind ergänzend und schreibgeschützt. Änderungen im Stadtplaner verändern OpenStreetMap nicht.' }
        ]
      },
      {
        id: 'keine-daten-oder-fehler',
        title: 'Keine Daten oder Fehler',
        blocks: [
          { type: 'list', items: ['„Keine Informationen“ bedeutet, dass aktuell kein passendes Objekt gefunden wurde.', 'Bei einem vorübergehenden Fehler kann die Abfrage erneut gestartet werden.', 'Die Aktualität hängt vom Stand des lokalen Imports beziehungsweise des externen Dienstes ab.', 'Eine fehlende OSM-Angabe sagt nichts über die Gültigkeit der eigentlichen Flächendaten aus.'] },
          { type: 'links', items: [{ label: 'Technische OSM-Einrichtung im Repository', to: '/open-data', description: 'Allgemeine Informationen zu den offenen Daten des Projekts.' }] }
        ]
      },
      {
        id: 'als-flaeche-uebernehmen',
        title: 'Als Stadtplaner-Fläche übernehmen',
        blocks: [
          { type: 'paragraph', text: 'Angemeldete Konten können ein geladenes OSM-Objekt als Ausgangspunkt für eine eigene Stadtplaner-Fläche verwenden. Der Server lädt Geometrie und Tags anhand von OSM-Typ und ID aus der lokalen Datenbank; vom Browser behauptete OSM-Geometrien werden nicht akzeptiert.' },
          { type: 'paragraph', text: 'Bei OSM-Punkten wird zuerst eine passende umschließende Gebäude- oder Nutzfläche gesucht. Gibt es keine, führt Stadtplaner zum manuellen Zeichnen. Ein künstlicher Punkt-Buffer wird nie als reale Fläche gespeichert.' },
          { type: 'callout', variant: 'important', title: 'Zwei getrennte Datenebenen', text: 'Die OSM-Quelle bleibt unverändert und schreibgeschützt. Titel, Kategorie, Geometrie sowie Verwaltungs- und Marktdaten der übernommenen Stadtplaner-Fläche können danach entsprechend der Rollenberechtigung eigenständig gepflegt werden.' }
        ]
      },
      {
        id: 'osm-daten-ergaenzen',
        title: 'OpenStreetMap-Daten ergänzen',
        blocks: [
          { type: 'paragraph', text: 'Fehlende oder veraltete OSM-Informationen werden nicht in Stadtplaner bearbeitet. Die Aktion „OpenStreetMap-Daten verbessern“ führt nach einem bewussten Klick zu externen OSM-Werkzeugen.' },
          { type: 'list', items: ['StreetComplete eignet sich besonders für kleine, frageorientierte Ergänzungen direkt vor Ort auf Android.', 'Der iD-Editor auf openstreetmap.org eignet sich für umfangreichere Änderungen im Browser und wird möglichst auf die Position des gewählten Objekts zentriert.', 'Eine erforderliche OSM-Anmeldung erfolgt ausschließlich bei OpenStreetMap; Stadtplaner speichert keine OSM-Zugangsdaten.'] },
          { type: 'callout', variant: 'tip', title: 'Tipp für Beiträge vor Ort', text: 'Wenn Sie direkt am Objekt stehen und nur fehlende Informationen ergänzen möchten, ist StreetComplete häufig der einfachste Einstieg.' },
          { type: 'links', items: [{ label: 'StreetComplete', to: 'https://streetcomplete.app/', description: 'OpenStreetMap-Editor für Android.' }, { label: 'OpenStreetMap bearbeiten', to: 'https://www.openstreetmap.org/edit?editor=id', description: 'Browserbasierter iD-Editor.' }] }
        ]
      }
    ]
  },
  {
    slug: 'flaechen',
    title: 'Verkaufsflächen und Flächendetails',
    navTitle: 'Verkaufsflächen',
    description: 'Was Stadtplaner-Flächen sind und welche öffentlichen Angaben, Geometrien und Detailseiten sie besitzen.',
    group: 'Karte und Daten',
    keywords: ['Verkaufsfläche', 'Fläche', 'Detailseite', 'Adresse', 'Geometrie', 'Beschreibung', 'Stadtplaner'],
    audience: 'public',
    sections: [
      {
        id: 'was-ist-eine-stadtplaner-flaeche',
        title: 'Was ist eine Stadtplaner-Fläche?',
        blocks: [
          { type: 'paragraph', text: 'Eine Stadtplaner-Fläche ist eine im Projekt angelegte und eigenständig gepflegte räumliche Fläche. Sie kann manuell gezeichnet oder aus einem vorhandenen OpenStreetMap-Objekt übernommen worden sein. Nach der Übernahme bleibt sie ein eigener Stadtplaner-Datensatz; Änderungen daran verändern OpenStreetMap nicht.' },
          { type: 'callout', variant: 'info', title: 'Gebäude ist nicht automatisch Verkaufsfläche', text: 'Eine Gebäudegeometrie oder ein anderes OSM-Polygon beweist für sich allein keine Verkaufsflächennutzung. Der Stadtplaner stellt diese Datenebenen deshalb getrennt dar.' }
        ]
      },
      {
        id: 'oeffentliche-angaben',
        title: 'Öffentliche Angaben',
        blocks: [
          { type: 'list', items: ['Name und Beschreibung', 'Branche, Größenklasse und Etage', 'Belegungsstatus und Betriebsform', 'Fläche und Umfang der Geometrie', 'Adresse, soweit ermittelt', 'POIs im gewählten Radius und nächster ÖPNV', 'Vergleichbare Flächen auf Abruf', 'Zeitpunkt der letzten Aktualisierung'] },
          { type: 'callout', variant: 'info', title: 'Leere Felder', text: 'Nicht vorhandene Werte werden ausgelassen oder mit einem neutralen Platzhalter angezeigt. Das ist kein technischer Fehler.' }
        ]
      },
      {
        id: 'neue-flaeche-anlegen',
        title: 'Neue Fläche anlegen',
        audience: 'login',
        blocks: [
          { type: 'paragraph', text: 'Angemeldete aktive Konten erreichen den Erstellungsbereich über „Neue Fläche“ direkt in der Kartenoberfläche. Die öffentliche Kartenübersicht bleibt dabei vollständig schreibgeschützt.' },
          { type: 'code', code: '/flaechen/neu', language: 'Route' },
          { type: 'steps', items: [{ title: 'Polygon zeichnen', text: 'Setzen Sie auf der Karte mindestens drei Eckpunkte und schließen Sie die Form am ersten Punkt.' }, { title: 'Angaben ergänzen', text: 'Wählen Sie Etage und Kategorie und vergeben Sie einen Titel.' }, { title: 'Fläche erstellen', text: 'Die Schaltfläche wird erst mit einer fertigen Geometrie aktiv. Der erste Speichervorgang ist ein einmaliges Erstellen, noch kein Autosave.' }, { title: 'Details weiterpflegen', text: 'Nach erfolgreicher Erstellung öffnet die Anwendung die dauerhafte Detailseite. Ab dort gilt das normale Autosave.' }] },
          { type: 'links', items: [{ label: 'Neue Fläche öffnen', to: '/flaechen/neu', description: 'Anmeldung erforderlich.' }] }
        ]
      },
      {
        id: 'adresse-und-geometrie',
        title: 'Adresse und Geometrie',
        blocks: [
          { type: 'paragraph', text: 'Die Fläche wird als Polygon dargestellt. Nach einer Geometrieänderung versucht der Server, anhand eines repräsentativen Punktes eine Adresse zu bestimmen. Die Geometrie kann auch gespeichert werden, wenn die externe Adresssuche vorübergehend nicht erreichbar ist.' },
          { type: 'callout', variant: 'warning', title: 'Adresse prüfen', text: 'Automatisch ermittelte Adressen können bei großen, verwinkelten oder grundstücksübergreifenden Flächen ungenau sein.' }
        ]
      },
      {
        id: 'dauerhafter-link',
        title: 'Dauerhafter Link',
        blocks: [
          { type: 'paragraph', text: 'Jede Fläche besitzt einen eindeutigen Slug in der URL. Dieser bleibt nach einer späteren Umbenennung erhalten, damit bereits geteilte Links weiterhin funktionieren.' },
          { type: 'code', code: '/flaechen/<slug>', language: 'URL-Schema' },
          { type: 'links', items: [{ label: 'Flächen bearbeiten', to: '/dokumentation/flaechen-bearbeiten' }, { label: 'OpenStreetMap-Angaben', to: '/dokumentation/openstreetmap' }] }
        ]
      }
    ]
  },
  {
    slug: 'flaechen-bearbeiten',
    title: 'Flächen bearbeiten',
    navTitle: 'Bearbeiten',
    description: 'Öffentliche Attribute und Polygon-Geometrie sicher ändern und speichern.',
    group: 'Konto und Bearbeitung',
    keywords: ['Autosave', 'Editor', 'TerraDraw', 'Konflikt', 'Vertex', 'Eckpunkt'],
    audience: 'login',
    sections: [
      {
        id: 'voraussetzungen',
        title: 'Voraussetzungen',
        audience: 'login',
        blocks: [
          { type: 'paragraph', text: 'Die Bearbeitungsschaltflächen erscheinen nur bei einem angemeldeten und per E-Mail verifizierten Konto, das für die jeweilige Fläche bearbeitungsberechtigt ist. Das Anlegen und Löschen einer eigenen Fläche erfordert ein aktives angemeldetes Konto; die Rolle VERWALTUNG besitzt erweiterte Rechte.' },
          { type: 'links', items: [{ label: 'Rollen und Berechtigungen', to: '/dokumentation/rollen' }] }
        ]
      },
      {
        id: 'attribute-bearbeiten',
        title: 'Attribute bearbeiten',
        blocks: [
          { type: 'steps', items: [{ title: 'Detailseite öffnen', text: 'Rufen Sie die gewünschte Fläche über die Karte oder „Meine Flächen“ auf.' }, { title: 'Wert ändern', text: 'Bearbeiten Sie die freigegebenen Text- oder Auswahlfelder.' }, { title: 'Speicherstatus beobachten', text: 'Textänderungen werden nach einer kurzen Eingabepause gespeichert, Auswahlfelder unmittelbar.' }] },
          { type: 'paragraph', text: 'Der Status unterscheidet zwischen nicht gespeichert, wird gespeichert, gespeichert, Fehler und Konflikt. Nach einem normalen Fehler kann der Speichervorgang erneut versucht werden.' }
        ]
      },
      {
        id: 'polygon-bearbeiten',
        title: 'Polygon bearbeiten',
        blocks: [
          { type: 'steps', items: [{ title: 'Editor starten', text: 'Wählen Sie auf der Detailkarte „Polygon bearbeiten“.' }, { title: 'Geometrie anpassen', text: 'Ziehen Sie das Polygon oder einzelne Eckpunkte. Zwischenpunkte dienen dazu, weitere Eckpunkte einzufügen; ausgewählte, entbehrliche Punkte können im Editor entfernt werden.' }, { title: 'Bearbeitung abschließen', text: 'Beenden Sie den Bearbeitungsmodus. Erst dann wird die neue Geometrie an den Server übergeben.' }] },
          { type: 'callout', variant: 'warning', title: 'Geometrie sorgfältig prüfen', text: 'Achten Sie auf eine geschlossene, nicht selbst überschneidende Form. Versehentliche großräumige Verschiebungen sollten vor dem Abschluss korrigiert werden.' }
        ]
      },
      {
        id: 'konflikte',
        title: 'Gleichzeitige Änderungen und Konflikte',
        blocks: [
          { type: 'paragraph', text: 'Die Anwendung schützt neuere Serverdaten mit einer Versionsprüfung. Wenn eine andere Person dieselbe Fläche zwischenzeitlich geändert hat, wird Ihre veraltete Änderung nicht still überschrieben.' },
          { type: 'callout', variant: 'info', title: 'Bei einem Konflikt', text: 'Laden Sie die aktuelle Fassung neu, prüfen Sie die fremden Änderungen und führen Sie Ihre Anpassung anschließend erneut aus.' }
        ]
      },
      {
        id: 'adressaktualisierung',
        title: 'Adressaktualisierung',
        blocks: [
          { type: 'paragraph', text: 'Nach einer Geometrieänderung kann der Server die öffentliche Adresse neu ermitteln. Ein Ausfall der Adresssuche verhindert das Speichern der gültigen Geometrie nicht; die Adresse kann dann unverändert oder leer bleiben.' }
        ]
      },
      {
        id: 'flaeche-loeschen',
        title: 'Fläche löschen',
        audience: 'login',
        blocks: [
          { type: 'paragraph', text: 'Der technische Ersteller darf seine eigene Fläche löschen. Konten mit der Rolle VERWALTUNG dürfen jede Fläche löschen. Für andere angemeldete Konten wird der Gefahrenbereich nicht angezeigt und der Server lehnt einen direkten Löschversuch ab.' },
          { type: 'steps', items: [{ title: 'Gefahrenbereich öffnen', text: 'Scrollen Sie auf der Detailseite bis zum Abschnitt „Gefahrenbereich“.' }, { title: 'Löschen wählen', text: 'Betätigen Sie „Fläche löschen“ und prüfen Sie Titel und Warnhinweis im Dialog.' }, { title: 'Endgültig bestätigen', text: 'Nach der Bestätigung wird die Fläche dauerhaft entfernt und die Kartenübersicht geöffnet.' }] },
          { type: 'callout', variant: 'important', title: 'Nicht rückgängig zu machen', text: 'Die Löschung entfernt die Fläche dauerhaft. Brechen Sie den Dialog ab, wenn Sie sich nicht sicher sind.' }
        ]
      }
    ]
  },
  {
    slug: 'statistik',
    title: 'Kommunale Statistik',
    navTitle: 'Kommunale Statistik',
    description: 'Bevölkerung, Haushalte, Zeitreihen, Quellen und Statistikgebiete verständlich einordnen.',
    group: 'Karte und Daten',
    keywords: ['Statistik', 'Bevölkerung', 'Einwohner', 'Haushalte', 'Zeitreihe', 'Periode', 'Zahlenspiegel'],
    audience: 'public',
    sections: [
      {
        id: 'herkunft-und-anzeige',
        title: 'Woher kommen die Statistikwerte?',
        blocks: [
          { type: 'paragraph', text: 'Der Stadtplaner importiert veröffentlichte Bevölkerungs- und Haushaltsdaten aus dem Zahlenspiegel der Stadt Flensburg. Die Anwendung zeigt lokal gespeicherte Werte und fragt das Statistikportal nicht bei jedem Seitenaufruf live ab.' },
          { type: 'list', items: ['Jeder Wert besitzt eine Berichtsperiode.', 'Die Quelle und der verfügbare Datenstand werden angezeigt.', 'Zeitreihen enthalten nur tatsächlich veröffentlichte Perioden.', 'Fehlende oder unterdrückte Werte werden nicht zurückgerechnet.'] }
        ]
      },
      {
        id: 'statistikgebiete',
        title: 'Für welches Gebiet gilt ein Wert?',
        blocks: [
          { type: 'paragraph', text: 'Die Statistik ist für die Gesamtstadt und die zugeordneten Stadtteile verfügbar. Quartiere besitzen derzeit keine künstlich verteilten eigenen Werte.' },
          { type: 'callout', variant: 'important', title: 'Wert des übergeordneten Gebiets', text: 'Für ein Quartier kann deshalb der veröffentlichte Wert des übergeordneten Stadtteils erscheinen. Der Stadtplaner nennt sowohl das angefragte Gebiet als auch das tatsächlich verwendete Statistikgebiet. Der Wert wird nicht als eigene Erhebung des Quartiers dargestellt.' },
          { type: 'paragraph', text: 'Statistische Gebietseinteilung und Kartengrenze haben passende Bezeichnungen. Eine geometrisch vollständig identische Abgrenzung ist damit jedoch nicht automatisch belegt.' }
        ]
      },
      {
        id: 'statistik-und-auswertung',
        title: 'Statistik und berechnete Auswertung unterscheiden',
        blocks: [
          { type: 'table', headers: ['Beispiel', 'Art der Angabe', 'Datengrundlage'], rows: [['Bevölkerung und Haushalte', 'Kommunale Statistik', 'Veröffentlichter Zahlenspiegel'], ['POI-Anzahl', 'Räumliche Auswertung', 'Lokal importierte OpenStreetMap-Objekte'], ['Leerstandsquote', 'Berechnete Kennzahl oder veröffentlichter Referenzwert', 'Flächen mit bekanntem Status beziehungsweise gepflegte Quelle']] },
          { type: 'links', items: [{ label: 'Kennzahlen verstehen', to: '/dokumentation/fast-facts' }, { label: 'Datenquellen und Aktualität', to: '/dokumentation/datenquellen' }] }
        ]
      }
    ]
  },
  {
    slug: 'datenquellen',
    title: 'Datenquellen und Aktualität',
    navTitle: 'Datenquellen',
    description: 'Herkunft, Datenstand und Qualitätsgrenzen von Stadtplaner-Flächen, OpenStreetMap und kommunaler Statistik.',
    group: 'Karte und Daten',
    keywords: ['Datenquelle', 'Daten aktuell', 'Aktualität', 'Datenstand', 'OSM', 'OpenStreetMap', 'Statistik', 'Qualität', 'null', 'UNKNOWN'],
    audience: 'public',
    sections: [
      {
        id: 'quellen-im-vergleich',
        title: 'Datenquellen im Vergleich',
        blocks: [
          { type: 'table', headers: ['Aspekt', 'Stadtplaner', 'OpenStreetMap'], rows: [['Pflege', 'Eigene, berechtigungsgeschützt gepflegte Flächen', 'Gemeinschaftlich gepflegte offene Geodaten'], ['Geschäftsflächen', 'Als Stadtplaner-Flächen mit eigener Detailseite', 'Ergänzende Geschäftsobjekte, sofern passende Tags vorhanden sind'], ['POIs', 'Umfeld- und Standortauswertungen', 'Quelle der lokal importierten POIs'], ['Gebäude', 'Keine automatische Behauptung einer Verkaufsfläche', 'Separat einblendbare OSM-Gebäudegeometrien'], ['Belegungsstatus', 'Kann ausdrücklich gepflegt sein', 'Nur aus kontrollierten eindeutigen Tags abgeleitet'], ['Aktualität', 'Zeitpunkt der letzten Änderung ist sichtbar', 'Abhängig vom lokalen OSM-Import und der OSM-Datenpflege']] },
          { type: 'callout', variant: 'info', title: 'Analysegebiete sind eine eigene Ebene', text: 'Gemeinden, Stadtteile und Quartiere sind fachliche Analysegebiete. Ein gewöhnliches OpenStreetMap-Objekt wird nicht automatisch zu einem Analysegebiet.' }
        ]
      },
      {
        id: 'weitere-quellen',
        title: 'Kommunale Statistik und manuelle Kennzahlen',
        blocks: [
          { type: 'paragraph', text: 'Kommunale Statistik wird mit Quelle und Berichtsperiode importiert. Zentralität, Kaufkraft und gegebenenfalls veröffentlichte Referenzquoten können als eigenständige Stadtkennzahlen mit Quelle und Referenzdatum gepflegt sein.' },
          { type: 'paragraph', text: 'Es gibt kein pauschal garantiertes Aktualisierungsintervall für alle Quellen. Beachten Sie deshalb den jeweils angezeigten Änderungszeitpunkt, Datenstand oder die Berichtsperiode.' }
        ]
      },
      {
        id: 'fehlend-unbekannt-null',
        title: 'Fehlend, unbekannt und null',
        blocks: [
          { type: 'table', headers: ['Anzeige', 'Bedeutung'], rows: [['0', 'Ein vorhandener Wert mit dem Zahlenwert null.'], ['Nicht angegeben oder Gedankenstrich', 'Es liegt keine belastbare Zahl vor.'], ['Unbekannt', 'Der fachliche Status ist nicht ausreichend bekannt.'], ['Keine Treffer', 'Die aktuelle Auswahl enthält keine passenden Objekte; das ist nicht automatisch ein Datenfehler.']] },
          { type: 'callout', variant: 'important', title: 'Keine Gleichsetzung', text: 'Unbekannt bedeutet nicht belegt. Ein fehlender Wert bedeutet nicht null. Unterschiedliche Quellen können außerdem einen unterschiedlichen Datenstand besitzen.' },
          { type: 'links', items: [{ label: 'Daten fehlen oder sind falsch', to: '/dokumentation/faq#daten-korrigieren' }] }
        ]
      }
    ]
  },
  {
    slug: 'leerstand',
    title: 'Leerstand und Belegungsstatus',
    navTitle: 'Leerstand',
    description: 'Belegt, leerstehend und unbekannt unterscheiden und die Leerstandsquote richtig lesen.',
    group: 'Analyse',
    keywords: ['Leerstand', 'Belegungsstatus', 'leerstehend', 'belegt', 'unbekannt', 'VACANT', 'OCCUPIED', 'UNKNOWN', 'Leerstandsquote'],
    audience: 'public',
    sections: [
      {
        id: 'statuswerte',
        title: 'Drei mögliche Statusangaben',
        blocks: [
          { type: 'table', headers: ['Anzeige', 'Bedeutung'], rows: [['Belegt', 'Die Stadtplaner-Fläche ist ausdrücklich als belegt gepflegt.'], ['Leerstehend', 'Die Fläche oder das OSM-Objekt wurde nach den vorhandenen Regeln ausdrücklich als leerstehend erkannt.'], ['Unbekannt', 'Der Belegungsstatus ist nicht ausreichend bekannt.']] },
          { type: 'callout', variant: 'important', title: 'Unbekannt ist nicht belegt', text: 'Das Fehlen eines Leerstandshinweises reicht nicht aus, um ein Objekt als belegt zu zählen.' }
        ]
      },
      {
        id: 'osm-ableitung',
        title: 'Leerstand aus OpenStreetMap',
        blocks: [
          { type: 'paragraph', text: 'Bei OpenStreetMap berücksichtigt der Stadtplaner nur kontrollierte Lifecycle-Angaben mit passendem Gewerbekontext, beispielsweise shop=vacant, disused:shop oder disused=yes. Fehlen eindeutige Angaben, bleibt der Status unbekannt.' },
          { type: 'links', items: [{ label: 'OpenStreetMap im Stadtplaner', to: '/dokumentation/openstreetmap' }] }
        ]
      },
      {
        id: 'leerstandsquote',
        title: 'Leerstandsquote',
        blocks: [
          { type: 'paragraph', text: 'Die berechnete Leerstandsquote teilt die Zahl der leerstehenden Flächen durch alle Flächen mit bekanntem Belegungsstatus. Flächen mit unbekanntem Status werden weder als leerstehend noch als belegt in den Nenner aufgenommen.' },
          { type: 'callout', variant: 'info', title: 'Berechnet oder gepflegt', text: 'Wenn die aktuelle Auswahl eine Quote aus bekannten Flächenstatus berechnen lässt, wird diese verwendet. Andernfalls kann für die Gesamtstadt ein veröffentlichter Referenzwert mit Quelle angezeigt werden. Die Oberfläche kennzeichnet die Datengrundlage.' }
        ]
      }
    ]
  },
  {
    slug: 'branchen-und-pois',
    title: 'Branchen, Kategorien und POIs',
    navTitle: 'Branchen und POIs',
    description: 'Branchenfilter, Kategorien und ergänzende OpenStreetMap-Orte voneinander unterscheiden.',
    group: 'Analyse',
    keywords: ['Branche', 'Kategorie', 'POI', 'Gastronomie', 'Mode', 'Lebensmittel', 'Dienstleistung', 'Geschäft'],
    audience: 'public',
    sections: [
      {
        id: 'branchen',
        title: 'Verfügbare Branchen',
        blocks: [
          { type: 'paragraph', text: 'Stadtplaner-Flächen und passende OSM-Geschäftsobjekte verwenden eine gemeinsame nutzerfreundliche Branchenauswahl.' },
          { type: 'table', headers: ['Branche', 'Beispiele'], rows: [['Warenhaus', 'Warenhäuser'], ['Mode / Bekleidung', 'Bekleidungsgeschäfte'], ['Nahrungsmittel / Drogerie', 'Lebensmittel und Drogeriewaren'], ['Elektro / Technik', 'Elektro- und Technikgeschäfte'], ['Einrichtungsbedarf', 'Möbel und Einrichtung'], ['Garten / Freizeit', 'Garten- und Freizeitangebote'], ['Sonstige Waren', 'Weitere Warenangebote'], ['Gastronomie', 'Restaurants, Cafés, Bars und ähnliche Angebote'], ['Einzelhandelsnahe Dienstleister', 'Dienstleistungen mit Bezug zum Standort'], ['Sonstige Flächen', 'Nicht anderweitig zugeordnete Flächen']] },
          { type: 'paragraph', text: 'Die genaue Zuordnung von OSM-Tags erfolgt über die kontrollierte Mappinglogik des Stadtplaners. Ein unbekannter älterer Kategorienwert bleibt sichtbar und erhält keine erfundene Zuordnung.' }
        ]
      },
      {
        id: 'pois',
        title: 'Was sind POIs?',
        blocks: [
          { type: 'paragraph', text: 'POI steht für „Point of Interest“, also einen relevanten Ort. Dazu können beispielsweise Haltestellen, Parkmöglichkeiten, Kultur-, Bildungs- oder Versorgungsangebote gehören. POIs ergänzen die Standortanalyse und sind nicht automatisch Verkaufsflächen.' },
          { type: 'paragraph', text: 'POI-Zahlen werden aus den lokal importierten OpenStreetMap-Objekten innerhalb des betrachteten Gebiets oder Umkreises ermittelt. Aktive Geschäftsfilter und reine Umfeld-POIs bleiben fachlich getrennt.' }
        ]
      }
    ]
  },
  {
    slug: 'fast-facts',
    title: 'Kennzahlen und Auswertungen',
    navTitle: 'Kennzahlen',
    description: 'Bedeutung, Herkunft und Filterverhalten der Kennzahlen.',
    group: 'Analyse',
    keywords: ['Leerstand', 'Leerstandsquote', 'Filialisierung', 'Zentralität', 'Kaufkraft', 'POI', 'Median', 'Durchschnitt', 'Standorte', 'Kennzahlen', 'Analytics'],
    audience: 'public',
    sections: [
      {
        id: 'berechnete-werte',
        title: 'Aus Flächen berechnete Werte',
        blocks: [
          { type: 'paragraph', text: 'Anzahl der Verkaufsflächen, Gesamt- und Durchschnittsfläche, Branchenverteilung sowie – bei bekannten Objektattributen – Leerstands- und Filialisierungsquote werden aus den erfassten Flächen berechnet. Aktive Kartenfilter wirken auf diese Auswertung; unbekannte Statuswerte werden aus dem jeweiligen Quotienten ausgeschlossen.' },
          { type: 'links', items: [{ label: 'Gebiete vergleichen', to: '/vergleich', description: 'Bis zu vier Gemeinden, Stadtteile oder Quartiere mit optionaler Gesamtstadt-Referenz vergleichen.' }] }
        ]
      },
      {
        id: 'gebietsvergleich',
        title: 'Gebiete vergleichen',
        blocks: [
          { type: 'paragraph', text: 'Im Gebietsvergleich wählen Sie bis zu vier Gemeinden, Stadtteile oder Quartiere. Die Gesamtstadt kann zusätzlich als Referenz eingeblendet werden. Alle Kennzahlen werden über die konkrete Gebietszuordnung der Stadtplaner-Flächen berechnet.' },
          { type: 'steps', items: [{ title: 'Gebiete wählen', text: 'Suchen Sie nach dem Namen eines Gebiets und fügen Sie mindestens zwei Vergleichspartner hinzu.' }, { title: 'Referenz festlegen', text: 'Blenden Sie Flensburg als Gesamtstadt-Referenz ein, wenn ein einzelnes Gebiet mit dem kommunalen Wert verglichen werden soll.' }, { title: 'Optional filtern', text: 'Öffnen Sie „Vergleich einschränken“. Die gewählten Filter gelten identisch für alle Gebiete.' }] },
          { type: 'callout', variant: 'info', title: 'Teilbarer Vergleich', text: 'Ausgewählte Gebiete, Referenz und Filter stehen in der URL. Kopieren Sie die Adresse, um denselben Vergleich zu teilen.' }
        ]
      },
      {
        id: 'gepflegte-werte',
        title: 'Manuell gepflegte Stadtkennzahlen',
        blocks: [
          { type: 'table', headers: ['Kennzahl', 'Darstellung'], rows: [['Leerstand', 'Prozentwert'], ['Filialisierung', 'Prozentwert'], ['Zentralität', 'Index'], ['Kaufkraft', 'Index']] },
          { type: 'paragraph', text: 'Zentralität und Kaufkraft sowie gegebenenfalls veröffentlichte Referenzquoten werden von der Verwaltung mit Referenzdatum und Quelle gepflegt. Wenn Flächenattribute eine Quote berechenbar machen, zeigt die Übersicht vorrangig die berechnete Quote und kennzeichnet ihre Datengrundlage.' },
          { type: 'callout', variant: 'info', title: 'Fehlender Wert', text: 'Ein Gedankenstrich bedeutet, dass derzeit kein veröffentlichbarer Wert hinterlegt ist. Er bedeutet nicht automatisch null Prozent.' }
        ]
      },
      {
        id: 'datenstand',
        title: 'Datenstand und Einordnung',
        blocks: [
          { type: 'paragraph', text: 'Der angezeigte Stand und die veröffentlichte Quelle helfen, Kennzahlen zeitlich einzuordnen. Interne Verwaltungsnotizen bleiben ausschließlich im Verwaltungsbereich sichtbar.' },
          { type: 'links', items: [{ label: 'Kennzahlen verwalten', to: '/dokumentation/verwaltung' }, { label: 'Filterverhalten', to: '/dokumentation/filter' }] }
        ]
      }
    ]
  },
  {
    slug: 'benutzerkonto',
    title: 'Benutzerkonto und Profil',
    navTitle: 'Benutzerkonto',
    description: 'Registrierung, E-Mail-Bestätigung, Profil, Avatar und Kontosicherheit einschließlich Deaktivierung und Löschung.',
    group: 'Konto und Bearbeitung',
    keywords: ['Registrierung', 'Login', 'Passwort', 'Avatar', 'Profil', 'E-Mail'],
    audience: 'login',
    sections: [
      {
        id: 'registrieren-und-anmelden',
        title: 'Registrieren und anmelden',
        blocks: [
          { type: 'steps', items: [{ title: 'Konto erstellen', text: 'Geben Sie die erforderlichen Kontaktdaten und ein Passwort in der Registrierung ein.' }, { title: 'E-Mail bestätigen', text: 'Öffnen Sie den Bestätigungslink aus der E-Mail. Eine neue Bestätigung kann bei Bedarf angefordert werden.' }, { title: 'Anmelden', text: 'Verwenden Sie E-Mail-Adresse und Passwort oder einen angebotenen externen Anmeldedienst.' }] },
          { type: 'paragraph', text: 'Über „Passwort vergessen“ kann ein zeitlich begrenzter Link zum Setzen eines neuen Passworts angefordert werden.' }
        ]
      },
      {
        id: 'profil-und-avatar',
        title: 'Profil und Avatar',
        blocks: [
          { type: 'paragraph', text: 'Im Profil lassen sich Vorname, Nachname und Anzeigename pflegen. Als Avatar werden JPG-, PNG- und WebP-Dateien bis zur in der Anwendung angegebenen Maximalgröße akzeptiert; aktuell sind das in der Regel 5 MB.' },
          { type: 'paragraph', text: 'Ein Avatar kann ersetzt oder entfernt werden. Ohne Bild verwendet die Oberfläche eine neutrale Darstellung beziehungsweise Initialen.' }
        ]
      },
      {
        id: 'email-bestaetigen',
        title: 'E-Mail-Bestätigung',
        blocks: [
          { type: 'paragraph', text: 'Der Bestätigungslink ist für die einmalige Verifikation der E-Mail-Adresse vorgesehen. Ist das Konto bereits bestätigt, ist kein erneutes Bestätigen erforderlich. Eine neue Bestätigungs-Mail kann nur für ein noch nicht bestätigtes Konto angefordert werden.' }
        ]
      },
      {
        id: 'sicherheit',
        title: 'Sicherheit und Sitzungen',
        blocks: [
          { type: 'paragraph', text: 'Im Sicherheitsbereich kann das Passwort mit dem aktuellen Passwort geändert werden. „Alle Sitzungen abmelden“ beendet bestehende Anmeldungen auf anderen Geräten ebenfalls.' },
          { type: 'callout', variant: 'tip', title: 'Geteiltes Gerät', text: 'Melden Sie sich nach der Nutzung vollständig ab und speichern Sie das Passwort nicht in einem fremden Browser.' }
        ]
      },
      {
        id: 'konto-deaktivieren-und-loeschen',
        title: 'Konto deaktivieren oder löschen',
        blocks: [
          { type: 'paragraph', text: 'Im Gefahrenbereich am Ende des Profils stehen zwei getrennte Aktionen zur Verfügung. Beim Deaktivieren wird der Login sofort gesperrt und alle Sitzungen werden beendet; Kontodaten und bisherige Beiträge bleiben bestehen. Wenn Sie anschließend erneut eine Anmeldung versuchen, weist Stadtplaner verständlich auf die selbst vorgenommene Deaktivierung hin. Eine Reaktivierung ist über die Administration beziehungsweise den Support möglich.' },
          { type: 'paragraph', text: 'Die dauerhafte Löschung entfernt persönliche Profildaten, Passwort, externe Kontoverknüpfungen, Sitzungen, Einmal-Tokens und den lokalen Avatar. Sie erfordert eine zweistufige Bestätigung sowie bei Passwortkonten das aktuelle Passwort. Bei ausschließlich externer Anmeldung muss die Sitzung ausreichend aktuell sein.' },
          { type: 'callout', variant: 'important', title: 'Dauerhafte Aktion', text: 'Ein gelöschtes Konto kann nicht wiederhergestellt werden. Öffentliche fachliche Flächen bleiben als gemeinsame Datengrundlage ohne Verknüpfung zum gelöschten Konto erhalten. Auditdaten können im erforderlichen, minimierten Umfang für die Nachvollziehbarkeit bestehen bleiben.' },
          { type: 'links', items: [{ label: 'Profil und Gefahrenbereich öffnen', to: '/profil' }, { label: 'Datenschutzerklärung', to: '/datenschutz' }] }
        ]
      },
      {
        id: 'meine-flaechen',
        title: 'Meine Flächen',
        blocks: [
          { type: 'paragraph', text: 'Die Seite „Meine Flächen“ listet die dem angemeldeten Konto zugeordneten Einträge und führt zu deren Detailseiten. Eine Zuordnung allein ersetzt nicht die zusätzlich erforderliche Verifizierung für Änderungen.' },
          { type: 'links', items: [{ label: 'Flächen bearbeiten', to: '/dokumentation/flaechen-bearbeiten' }] }
        ]
      }
    ]
  },
  {
    slug: 'benachrichtigungen',
    title: 'Benachrichtigungen',
    navTitle: 'Benachrichtigungen',
    description: 'Persönliche Hinweise zu Flächen, Gebieten, Importen, Veröffentlichungen und Kontosicherheit.',
    group: 'Konto und Bearbeitung',
    keywords: ['Benachrichtigung', 'Glocke', 'Folgen', 'Ungelesen', 'Hinweise', 'Einstellungen'],
    audience: 'login',
    sections: [
      {
        id: 'notification-center',
        title: 'Notification Center verwenden',
        blocks: [
          { type: 'paragraph', text: 'Die Glocke im Kopfbereich zeigt die Zahl ungelesener Hinweise. Am Desktop öffnet sie ein kompaktes Panel, auf kleinen Bildschirmen ein Bottom Sheet. Ungelesene Einträge sind zusätzlich textlich und nicht nur durch Farbe gekennzeichnet.' },
          { type: 'list', items: ['Filtern Sie Hinweise nach Themenbereich oder zeigen Sie nur ungelesene Einträge.', 'Markieren Sie einzelne Einträge oder alle sichtbaren Hinweise als gelesen.', 'Ein vorhandenes Aktionsziel führt ausschließlich zu einer geprüften internen Stadtplaner-Seite.', 'Weitere Einträge werden seitenweise nachgeladen; das Panel bleibt dabei der einzige Scrollbereich.'] }
        ]
      },
      {
        id: 'flaechen-und-gebieten-folgen',
        title: 'Flächen und Gebieten folgen',
        blocks: [
          { type: 'paragraph', text: 'Auf Detailseiten können angemeldete Personen einer Fläche oder einem Gebiet folgen. Relevante Änderungen an diesem Objekt erscheinen anschließend im persönlichen Notification Center. Das Abonnement kann an derselben Stelle jederzeit beendet werden.' },
          { type: 'callout', variant: 'info', title: 'Keine Autosave-Flut', text: 'Mehrere gleichartige Änderungen desselben Objekts werden innerhalb eines kurzen Zeitfensters zu einem Hinweis zusammengeführt. Eigene gewöhnliche Bearbeitungsschritte erzeugen keinen persönlichen Hinweis.' }
        ]
      },
      {
        id: 'einstellungen',
        title: 'Themen einstellen',
        blocks: [
          { type: 'paragraph', text: 'Im Profil lassen sich Hinweise zu GIS-Flächen, OpenStreetMap, Gebietsstatistiken, Social Publishing und Systemvorgängen getrennt ein- oder ausschalten. Die Einstellungen gelten kontoweit.' },
          { type: 'callout', variant: 'important', title: 'Sicherheitshinweise bleiben aktiv', text: 'Kontorelevante Sicherheitsmeldungen, etwa zu Rollen oder einer Deaktivierung, können nicht über die allgemeinen Themenfilter abgeschaltet werden.' },
          { type: 'links', items: [{ label: 'Benachrichtigungseinstellungen öffnen', to: '/profil' }] }
        ]
      },
      {
        id: 'zustellung-und-datenschutz',
        title: 'Zustellung und Datenschutz',
        blocks: [
          { type: 'paragraph', text: 'Hinweise werden dauerhaft dem angemeldeten Konto zugeordnet und nach dem Laden in Echtzeit ergänzt. Nach einer unterbrochenen Verbindung gleicht die Anwendung den persistenten Stand erneut ab.' },
          { type: 'paragraph', text: 'Titel, Nachricht und Link verwenden kontrollierte Vorlagen. Interne Eigentümer-, Miet-, Kontakt- oder Authentifizierungsdaten werden nicht in Benachrichtigungstexte übernommen. Ein Benachrichtigungseintrag ist kein Auditlog: Das Auditlog dient der administrativen Nachvollziehbarkeit, das Notification Center ausschließlich der persönlichen Information.' }
        ]
      }
    ]
  },
  {
    slug: 'oauth',
    title: 'Anmeldung mit externen Diensten',
    navTitle: 'Externe Anmeldung',
    description: 'OAuth-Anmeldung sowie Verknüpfen und Trennen externer Konten.',
    group: 'Konto und Bearbeitung',
    keywords: ['OAuth', 'Google', 'GitHub', 'Mastodon', 'Provider', 'Verknüpfung'],
    audience: 'login',
    sections: [
      {
        id: 'verfuegbare-anbieter',
        title: 'Verfügbare Anbieter',
        blocks: [
          { type: 'paragraph', text: 'Externe Anmeldeschaltflächen erscheinen nur für Dienste, die auf dem Server eingerichtet und aktiviert sind. Unterstützt werden je nach Betrieb Google, GitHub und Mastodon.' },
          { type: 'paragraph', text: 'Für Mastodon geben Sie zunächst die Instanz an, auf der Ihr Konto liegt, zum Beispiel norden.social oder mastodon.social. Anschließend werden Sie zur Anmeldung auf genau diese Instanz weitergeleitet. Stadtplaner fragt kein Mastodon-Passwort ab.' },
          { type: 'callout', variant: 'info', title: 'Neue Anmeldung ohne E-Mail', text: 'Mastodon übermittelt keine verifizierte E-Mail-Adresse. Bei einem neuen Stadtplaner-Konto hinterlegen und bestätigen Sie die E-Mail deshalb anschließend im Profil.' },
          { type: 'callout', variant: 'info', title: 'Keine Schaltfläche sichtbar', text: 'Dann ist aktuell kein externer Anbieter konfiguriert. Die Anmeldung mit E-Mail-Adresse und Passwort bleibt davon unberührt.' }
        ]
      },
      {
        id: 'konto-verknuepfen',
        title: 'Externes Konto verknüpfen',
        blocks: [
          { type: 'paragraph', text: 'Im Profil können unterstützte externe Konten mit dem angemeldeten Stadtplaner-Konto verknüpft werden. Die Übersicht zeigt vorhandene Verknüpfungen und gegebenenfalls die übermittelte Kennung oder E-Mail-Adresse.' },
          { type: 'callout', variant: 'important', title: 'Verknüpfen nur im Profil', text: 'Das Verknüpfen eines externen Kontos findet im Profil eines bereits angemeldeten Kontos statt, nicht auf der Login-Seite.' },
          { type: 'links', items: [{ label: 'Profil öffnen', to: '/profil', description: 'Externe Konten des angemeldeten Kontos verwalten.' }] }
        ]
      },
      {
        id: 'verknuepfung-trennen',
        title: 'Verknüpfung trennen',
        blocks: [
          { type: 'paragraph', text: 'Eine nicht mehr benötigte Verknüpfung kann im Profil getrennt werden, sofern dadurch weiterhin ein zulässiger Zugang zum Konto bestehen bleibt. Prüfen Sie vorher, ob Sie Ihr Passwort kennen.' },
          { type: 'links', items: [{ label: 'Benutzerkonto und Sicherheit', to: '/dokumentation/benutzerkonto' }] }
        ]
      }
    ]
  },
  {
    slug: 'rollen',
    title: 'Rollen und Berechtigungen',
    navTitle: 'Rollen',
    description: 'Welche Bereiche öffentlich, nach Anmeldung oder nur für die Verwaltung erreichbar sind.',
    group: 'Konto und Bearbeitung',
    keywords: ['VERWALTUNG', 'Berechtigung', 'verifiziert', 'Eigentümer', 'Zugriff'],
    audience: 'public',
    sections: [
      {
        id: 'zugriffsmatrix',
        title: 'Zugriffsmatrix',
        blocks: [
          { type: 'table', headers: ['Funktion', 'Erforderlicher Zugriff'], rows: [['Karte, öffentliche Details, Kennzahlen und Hilfe lesen', 'Öffentlich'], ['Profil, eigene Flächen und neue Fläche öffnen', 'Angemeldet'], ['Eigene Fläche löschen', 'Angemeldet und technischer Ersteller'], ['Öffentliche Felder einer berechtigten Fläche ändern', 'Angemeldet, E-Mail bestätigt und bearbeitungsberechtigt'], ['Jede Fläche bearbeiten oder löschen', 'VERWALTUNG'], ['Interne Eigentümer- und Preisdaten sehen oder ändern', 'VERWALTUNG'], ['Stadtkennzahlen pflegen', 'VERWALTUNG'], ['Benutzerkonten und Rollen verwalten', 'SUPERUSER']] }
        ]
      },
      {
        id: 'verifizierung-und-zuordnung',
        title: 'Verifizierung und Zuordnung',
        blocks: [
          { type: 'paragraph', text: 'Eine Anmeldung allein erlaubt noch keine Flächenänderung. Der Server prüft sowohl die bestätigte E-Mail-Adresse als auch die konkrete Bearbeitungsberechtigung. Fehlende Schaltflächen sind deshalb häufig ein Hinweis auf eine noch offene Bestätigung oder Zuordnung.' }
        ]
      },
      {
        id: 'rolle-verwaltung',
        title: 'Rolle VERWALTUNG',
        audience: 'verwaltung',
        blocks: [
          { type: 'paragraph', text: 'VERWALTUNG ist eine serverseitig geprüfte Rolle. Nur diese Rolle sieht die Kennzahlenverwaltung und die internen Verwaltungsfelder auf Flächendetailseiten. Ein direkt eingegebener URL-Pfad umgeht diese Prüfung nicht.' },
          { type: 'links', items: [{ label: 'Verwaltungsfunktionen', to: '/dokumentation/verwaltung' }] }
        ]
      }
    ]
  },
  {
    slug: 'verwaltung',
    title: 'Verwaltungsfunktionen',
    navTitle: 'Verwaltung',
    description: 'Interne Flächenangaben und zentrale Stadtkennzahlen mit der Rolle VERWALTUNG pflegen.',
    group: 'Konto und Bearbeitung',
    keywords: ['VERWALTUNG', 'Eigentümer', 'Preis', 'Kennzahleneditor', 'Quelle', 'Notizen'],
    audience: 'verwaltung',
    sections: [
      {
        id: 'zugang',
        title: 'Zugang',
        audience: 'verwaltung',
        blocks: [
          { type: 'paragraph', text: 'Dieser Bereich setzt ein angemeldetes Konto mit der Rolle VERWALTUNG voraus. Die Oberfläche blendet Verwaltungslinks für andere Rollen aus; API und Seiten-Middleware prüfen den Zugriff zusätzlich.' },
          { type: 'callout', variant: 'warning', title: 'Interne Daten', text: 'Quellen, interne Notizen, fachliche Eigentümerdaten und Preise dürfen nicht in öffentliche Beschreibungsfelder kopiert werden, wenn sie nicht zur Veröffentlichung bestimmt sind.' }
        ]
      },
      {
        id: 'flaechenverwaltung',
        title: 'Interne Angaben einer Fläche',
        audience: 'verwaltung',
        blocks: [
          { type: 'paragraph', text: 'Auf der Flächendetailseite steht für VERWALTUNG ein eigener Abschnitt bereit. Dort können Belegungsstatus, Betriebsform, der fachliche Eigentümer, dessen Anschrift und ein Preis pro Quadratmeter gepflegt werden.' },
          { type: 'paragraph', text: 'Belegungsstatus und Betriebsform sind öffentliche fachliche Objektmerkmale für Filter und Aggregate. Eigentümer- und Preisfelder bleiben dagegen vollständig außerhalb öffentlicher Antworten und Suchmaschinen-Metadaten.' }
        ]
      },
      {
        id: 'kennzahlenverwaltung',
        title: 'Zentrale Kennzahlen pflegen',
        audience: 'verwaltung',
        blocks: [
          { type: 'code', code: '/verwaltung/kennzahlen', language: 'Route' },
          { type: 'steps', items: [{ title: 'Editor öffnen', text: 'Wählen Sie im Kontomenü „Kennzahlen verwalten“ oder öffnen Sie /verwaltung/kennzahlen.' }, { title: 'Werte eintragen', text: 'Pflegen Sie Leerstand, Filialisierung, Zentralität, Kaufkraft und das Referenzdatum. Prozentwerte und Indizes bleiben getrennte Größen.' }, { title: 'Herkunft dokumentieren', text: 'Ergänzen Sie Quelle und interne Notizen für die spätere Nachvollziehbarkeit.' }, { title: 'Explizit speichern', text: 'Prüfen Sie alle Werte und betätigen Sie „Speichern“. Anders als Flächenfelder nutzt dieser Editor kein Autosave.' }] },
          { type: 'callout', variant: 'info', title: 'Leere Eingabe', text: 'Ein geleertes optionales Kennzahlenfeld wird als nicht vorhanden gespeichert und erscheint öffentlich als Gedankenstrich, nicht als null.' }
        ]
      },
      {
        id: 'veroeffentlichung',
        title: 'Was wird veröffentlicht?',
        blocks: [
          { type: 'table', headers: ['Angabe', 'Öffentlich'], rows: [['Kennzahlenwerte, Referenzdatum und Quelle', 'Ja'], ['Interne Notizen der Kennzahlen', 'Nein'], ['Belegungsstatus und Betriebsform', 'Ja'], ['Fachlicher Eigentümer und Anschrift', 'Nein'], ['Preis pro Quadratmeter', 'Nein']] },
          { type: 'links', items: [{ label: 'Öffentliche Kennzahlen verstehen', to: '/dokumentation/fast-facts' }] }
        ]
      }
    ]
  },
  {
    slug: 'administration',
    title: 'Administration: Benutzer und Rollen',
    navTitle: 'Administration',
    description: 'Benutzerkonten suchen und die fachliche Rolle VERWALTUNG als Superuser sicher zuweisen oder entfernen.',
    group: 'Konto und Bearbeitung',
    keywords: ['SUPERUSER', 'Administration', 'Benutzer', 'Rollen', 'VERWALTUNG'],
    audience: 'superuser',
    sections: [
      {
        id: 'zugang-und-abgrenzung',
        title: 'Zugang und Abgrenzung',
        audience: 'superuser',
        blocks: [
          { type: 'paragraph', text: 'Die Benutzer- und Rollenverwaltung ist ausschließlich für Superuser erreichbar. Die fachliche Rolle VERWALTUNG allein gewährt keinen Zugang zu diesem Bereich.' },
          { type: 'callout', variant: 'important', title: 'Superuser ist keine normale Rolle', text: 'Der Superuser-Status wird in der Rollenverwaltung nur angezeigt. Er kann dort weder vergeben noch entfernt werden.' },
          { type: 'code', code: '/admin/benutzer', language: 'Route' }
        ]
      },
      {
        id: 'benutzer-finden',
        title: 'Benutzer suchen und filtern',
        audience: 'superuser',
        blocks: [
          { type: 'steps', items: [{ title: 'Administration öffnen', text: 'Wählen Sie im Kontomenü „Administration“.' }, { title: 'Benutzer suchen', text: 'Suchen Sie nach Name, Anzeigename oder vollständiger E-Mail-Adresse.' }, { title: 'Auswahl eingrenzen', text: 'Filtern Sie optional nach Rolle oder aktivem Kontostatus.' }, { title: 'Benutzer verwalten', text: 'Öffnen Sie die Detailansicht des gewünschten Kontos.' }] }
        ]
      },
      {
        id: 'rollen-aendern',
        title: 'VERWALTUNG zuweisen oder entfernen',
        audience: 'superuser',
        blocks: [
          { type: 'paragraph', text: 'Aktivieren oder deaktivieren Sie die Checkbox VERWALTUNG und bestätigen Sie die Sicherheitsabfrage. Die Änderung wird unmittelbar gespeichert und wirkt bei nachfolgenden API-Anfragen.' },
          { type: 'callout', variant: 'warning', title: 'Erweiterte fachliche Rechte', text: 'VERWALTUNG darf interne Eigentümer- und Preisdaten sehen, Stadtkennzahlen pflegen sowie alle Flächen bearbeiten und löschen. Vergeben Sie diese Rolle nur, wenn diese Rechte benötigt werden.' }
        ]
      },
      {
        id: 'auditlog',
        title: 'Administrative Änderungen nachvollziehen',
        audience: 'superuser',
        blocks: [
          { type: 'paragraph', text: 'Das Auditlog unter /admin/audit-log ist eine ausschließlich lesbare Superuser-Ansicht. Es protokolliert die im System vorhandenen administrativen Ereignisse, darunter Rollen- und Kontostatusänderungen sowie erkannte Refresh-Token-Wiederverwendung.' },
          { type: 'steps', items: [{ title: 'Auditlog öffnen', text: 'Wählen Sie im Kontomenü „Auditlog“.' }, { title: 'Einträge eingrenzen', text: 'Filtern Sie nach Aktion, ausführendem Benutzer und lokalem Zeitraum oder durchsuchen Sie Aktion, Benutzer und Ressource.' }, { title: 'Details prüfen', text: 'Öffnen Sie ein Ereignis, um Zusammenfassung, betroffene Ressource und vorhandene technische Details zu sehen.' }] },
          { type: 'callout', variant: 'info', title: 'Unveränderliche Historie', text: 'Die Ansicht bietet keine Funktion zum Bearbeiten oder Löschen. Nicht gespeicherte Angaben wie IP-Adresse oder User-Agent können auch in der Detailansicht nicht angezeigt werden.' }
        ]
      },
      {
        id: 'social-publishing',
        title: 'Mastodon-Veröffentlichungen überwachen',
        audience: 'superuser',
        blocks: [
          { type: 'paragraph', text: 'Unter /admin/social sehen Superuser den sicheren Verbindungsstatus, offene und fehlgeschlagene Outbox-Ereignisse sowie die Veröffentlichungshistorie. Dort lässt sich separat festlegen, ob künftig bewusst aus OpenStreetMap übernommene Flächen veröffentlicht werden und ob Beitrag und Pflicht-Screenshot auf die öffentliche Detailseite oder die GIS-Auswahl zeigen. Automatische Beiträge enthalten nur öffentliche Flächendaten; VERWALTUNG-, Eigentümer-, Miet-, Benutzer- und interne Felder bleiben ausgeschlossen. Der Access Token wird weder von der API zurückgegeben noch in der Oberfläche angezeigt.' },
          { type: 'steps', items: [{ title: 'Social Publishing öffnen', text: 'Wählen Sie im Kontomenü „Social Publishing“.' }, { title: 'Einstellungen anpassen', text: 'Änderungen an den Social-Publishing-Einstellungen werden automatisch gespeichert. Der Status zeigt „Speichern …“, „Gespeichert“ oder eine erneute Versuchsmöglichkeit.' }, { title: 'Status prüfen', text: 'Prüfen Sie Konfiguration, Erreichbarkeit, Dry-Run und Zähler.' }, { title: 'Fehler untersuchen', text: 'Fehlgeschlagene Ereignisse zeigen einen bereinigten Fehlertyp, aber keine Header oder Secrets.' }, { title: 'Erneut einreihen', text: 'Bestätigen Sie „Erneut versuchen“ im Dialog. Der Worker verwendet weiterhin denselben Idempotency-Key.' }] },
          { type: 'code', code: '/admin/social', language: 'Route' }
        ]
      }
    ]
  },
  {
    slug: 'gebiete',
    title: 'Gemeinde, Stadtteile und Quartiere',
    navTitle: 'Gebietsseiten',
    description: 'Gebietshierarchie, dauerhafte Detailseiten und der Wechsel zwischen Standortprofil und GIS-Karte.',
    group: 'Karte und Daten',
    keywords: ['Gemeinde', 'Stadtteil', 'Quartier', 'Gebiet', 'Standortprofil'],
    audience: 'public',
    sections: [
      {
        id: 'gebietsebenen',
        title: 'Drei Gebietsebenen',
        blocks: [
          { type: 'paragraph', text: 'Stadtplaner gliedert die kommunale Gebietskulisse in Gemeinde, Stadtteile und Quartiere. Jedes gültige Gebiet besitzt eine dauerhafte Seite unter /gebiete/<slug> und verweist auf über- und untergeordnete Gebiete.' },
          { type: 'list', items: ['Die Gemeinde bildet den kommunalen Bezugsrahmen.', 'Stadtteile sind der Gemeinde räumlich untergeordnet.', 'Quartiere sind einem Stadtteil räumlich untergeordnet.'] }
        ]
      },
      {
        id: 'detailseite-und-karte',
        title: 'Detailseite und GIS-Karte zusammen nutzen',
        blocks: [
          { type: 'steps', items: [{ title: 'Gebiet auswählen', text: 'Öffnen Sie die Gebietsübersicht oder wählen Sie eine Grenze in der GIS-Karte.' }, { title: 'Standortprofil lesen', text: 'Die Detailseite bündelt Kennzahlen, Branchen, POIs, Vergleichswerte und zugeordnete Flächen.' }, { title: 'In die Karte wechseln', text: '„In der Karte öffnen“ übernimmt das Gebiet als Auswahl und passt den Kartenausschnitt an.' }] },
          { type: 'links', items: [{ label: 'Gebietsübersicht öffnen', to: '/gebiete' }, { label: 'Methodik der Kennzahlen', to: '/dokumentation/methodik' }] }
        ]
      }
    ]
  },
  {
    slug: 'methodik',
    title: 'Datenqualität und Methodik',
    navTitle: 'Datenqualität',
    description: 'Räumliche Zuordnung, berechnete Kennzahlen und Grenzen der verfügbaren Daten verständlich einordnen.',
    group: 'Analyse',
    keywords: ['Methodik', 'Datenqualität', 'fehlende Daten', 'null', 'unbekannt', 'Leerstandsquote', 'POI', 'Statistik'],
    audience: 'public',
    sections: [
      {
        id: 'raeumliche-zuordnung',
        title: 'Räumliche Zuordnung',
        blocks: [
          { type: 'paragraph', text: 'Gebietsgrenzen werden als eigene Analysegebiete gepflegt und überwiegend aus OpenStreetMap synchronisiert. Eine Stadtplaner-Fläche wird anhand eines repräsentativen Punkts räumlich einem passenden Gebiet je Ebene zugeordnet.' },
          { type: 'callout', variant: 'info', title: 'Grenzen der Zuordnung', text: 'Eine Fläche kann eine Gebietsgrenze schneiden. Für die Auswertung zählt die Zuordnung über den repräsentativen Punkt; sie ist keine Aussage darüber, dass jeder Teil der Fläche vollständig innerhalb derselben Grenze liegt.' }
        ]
      },
      {
        id: 'kennzahlen',
        title: 'Kennzahlen berechnen',
        blocks: [
          { type: 'table', headers: ['Kennzahl', 'Berechnung'], rows: [['Leerstandsquote', 'Leer stehende Flächen geteilt durch Flächen mit bekanntem Belegungsstatus.'], ['Filialisierungsgrad', 'Filialbetriebe geteilt durch Flächen mit bekannter Betriebsform.'], ['Flächengrößen', 'Summe, arithmetischer Mittelwert und Median der räumlich zugeordneten Flächen.'], ['POIs', 'Anzahl lokal importierter OpenStreetMap-Objekte innerhalb der Gebietsgeometrie.']] },
          { type: 'callout', variant: 'important', title: 'Fehlend ist nicht null', text: 'Ein Gedankenstrich bedeutet, dass keine belastbare Zahl berechnet werden kann. Er ist nicht als Zahlenwert null zu interpretieren.' }
        ]
      },
      {
        id: 'unterschiedliche-datenstaende',
        title: 'Unterschiedliche Datenstände',
        blocks: [
          { type: 'paragraph', text: 'Stadtplaner-Flächen, OpenStreetMap und kommunale Statistik werden unabhängig voneinander gepflegt und aktualisiert. Unterschiede zwischen zwei Anzeigen können deshalb durch Quelle, räumliche Abgrenzung oder Datenstand entstehen.' },
          { type: 'callout', variant: 'important', title: 'Keine Schätzungen', text: 'Fehlende oder unterdrückte Angaben bleiben fehlend. Der Stadtplaner interpoliert keine Jahre, verteilt keine Stadtteilwerte auf Quartiere und setzt unbekannte Statusangaben nicht mit belegt gleich.' },
          { type: 'links', items: [{ label: 'Kommunale Statistik', to: '/dokumentation/statistik' }, { label: 'Datenquellen und Aktualität', to: '/dokumentation/datenquellen' }] }
        ]
      },
      {
        id: 'korrekturen',
        title: 'Daten prüfen und korrigieren',
        blocks: [
          { type: 'paragraph', text: 'Prüfen Sie bei auffälligen Angaben zuerst die genannte Quelle und den Datenstand. OpenStreetMap-Daten werden in OSM verbessert; Stadtplaner-Flächen über die vorhandenen Bearbeitungs- oder Kontaktwege. Statistikwerte folgen der veröffentlichten Originalquelle.' },
          { type: 'links', items: [{ label: 'Daten fehlen oder sind falsch', to: '/dokumentation/faq#daten-korrigieren' }] }
        ]
      }
    ]
  },
  {
    slug: 'api',
    title: 'Öffentliche API',
    navTitle: 'API',
    description: 'OpenAPI-Dokumentation und öffentliche Lese-Endpunkte für Gebiete und Stadtplaner-Flächen.',
    group: 'Quellcode und Entwicklung',
    keywords: ['API', 'OpenAPI', 'Swagger', 'ReDoc', 'JSON'],
    audience: 'public',
    sections: [
      {
        id: 'dokumentation',
        title: 'Interaktive API-Dokumentation',
        blocks: [
          { type: 'paragraph', text: 'Das FastAPI-Backend veröffentlicht sein OpenAPI-Schema sowie interaktive Dokumentationen unter /docs und /redoc relativ zur API-Origin. Öffentliche Lese-Endpunkte benötigen keine Anmeldung; schreibende und interne Endpunkte sind separat geschützt.' },
          { type: 'code', language: 'HTTP', code: 'GET /api/v1/polygons/overview?area_sizes=S,M&floors=EG,OG&categories=fashion,gastronomy&occupancy_statuses=VACANT\nGET /api/v1/osm/features?west=9.42&south=54.78&east=9.44&north=54.80&zoom=16&categories=fashion,gastronomy&floors=EG,OG\nGET /api/v1/analytics/overview?area_sizes=S,M&floors=EG,OG&sources=STADTPLANNER,OSM\nGET /api/v1/analysis-areas/{area_id}/analytics?area_sizes=S,M' },
          { type: 'paragraph', text: 'Die gemeinsamen Multi-Value-Parameter heißen categories, floors, area_sizes, occupancy_statuses, business_structures und sources. Der OSM-Viewport verwendet osm_categories separat für Umfeldlayer. Kommagetrennte Werte und wiederholte Parameter werden akzeptiert. Innerhalb eines Parameters gilt OR, zwischen Parametern AND; ungültige Enumwerte liefern HTTP 422.' }
        ]
      },
      {
        id: 'antworten',
        title: 'Antworten und Fehler',
        blocks: [
          { type: 'paragraph', text: 'Antworten werden als JSON ausgeliefert. Unbekannte Slugs liefern HTTP 404. Das OpenAPI-Schema ist die maßgebliche Referenz für Felder, Typen, Parameter und mögliche geschützte Operationen.' },
          { type: 'callout', variant: 'warning', title: 'Keine internen Felder', text: 'Die öffentlichen Gebiets- und Flächenantworten enthalten nur freigegebene Attribute. Eigentümer-, Preis- und andere Verwaltungsdaten werden nicht über diese Endpunkte ausgeliefert.' }
        ]
      },
      {
        id: 'quellcode',
        title: 'API-Quellcode und lokale Entwicklung',
        blocks: [
          { type: 'paragraph', text: 'Implementierung, Datenmodelle, Migrationen und lokale Einrichtungsanleitungen liegen im offiziellen Projekt-Repository. Das veröffentlichte OpenAPI-Schema bleibt die maßgebliche Referenz für die jeweils laufende Instanz.' },
          { type: 'links', items: [{ label: 'API-Quellcode auf GitHub', to: projectConfig.github.url, description: 'Repository in einem neuen Tab öffnen.', provider: 'github' }] }
        ]
      }
    ]
  },
  {
    slug: 'faq',
    title: 'Häufige Fragen',
    navTitle: 'FAQ',
    description: 'Kurze Antworten auf häufige Fragen zur Bedienung und zu Daten.',
    group: 'Hilfe',
    keywords: ['FAQ', 'Problem', 'Fehler', 'Hilfe', 'keine Daten', 'Gebäude', 'Statistik', 'Quartier', 'Korrektur', 'Konto'],
    audience: 'public',
    sections: [
      {
        id: 'keine-polygone',
        title: 'Warum sehe ich keine Polygone?',
        blocks: [
          { type: 'paragraph', text: 'Prüfen Sie zuerst die aktiven Größen-, Etagen- und Branchenfilter. Wenn auch ohne starke Einschränkung nichts erscheint, laden Sie die Seite neu und prüfen Sie die Netzwerkverbindung.' }
        ]
      },
      {
        id: 'bearbeiten-fehlt',
        title: 'Warum fehlt „Bearbeiten“?',
        blocks: [
          { type: 'paragraph', text: 'Sie müssen angemeldet, per E-Mail verifiziert und für genau diese Fläche berechtigt sein. Verwaltungsfelder setzen zusätzlich die Rolle VERWALTUNG voraus.' }
        ]
      },
      {
        id: 'verwaltungsdaten-fehlen',
        title: 'Warum sehe ich keine Verwaltungsdaten?',
        blocks: [
          { type: 'paragraph', text: 'Fachliche Eigentümerdaten, Eigentümeranschrift, Quadratmeterpreis sowie Quellen und interne Hinweise der Kennzahlen sind ausschließlich für Konten mit der Rolle VERWALTUNG sichtbar.' }
        ]
      },
      {
        id: 'speicherfehler',
        title: 'Was mache ich bei einem Speicherfehler?',
        blocks: [
          { type: 'paragraph', text: 'Versuchen Sie den Speichervorgang über die angebotene Schaltfläche erneut. Bei einem ausdrücklich gemeldeten Konflikt laden Sie den aktuellen Serverstand und wiederholen Ihre Änderung nach der Prüfung.' }
        ]
      },
      {
        id: 'osm-fehlt',
        title: 'Warum fehlen OpenStreetMap-Informationen?',
        blocks: [
          { type: 'paragraph', text: 'Es kann keinen passenden OSM-Eintrag geben, der lokale Import kann älter sein oder die Abfrage kann vorübergehend fehlschlagen. OSM-Angaben sind eine Ergänzung; die eigentliche Fläche bleibt davon unabhängig.' }
        ]
      },
      {
        id: 'gebaeude-fehlen',
        title: 'Warum sehe ich keine Gebäude?',
        blocks: [
          { type: 'paragraph', text: 'Aktivieren Sie die Gebäudeebene und zoomen Sie weiter hinein. Gebäude werden erst ab der dafür vorgesehenen Zoomstufe geladen. Fehlt eine Geometrie weiterhin, kann sie im lokalen OpenStreetMap-Datenstand nicht vorhanden sein.' }
        ]
      },
      {
        id: 'unbekannter-status',
        title: 'Warum ist ein Objekt als unbekannt gekennzeichnet?',
        blocks: [
          { type: 'paragraph', text: 'Für den betreffenden Status liegt keine ausreichende Angabe vor. Unbekannt wird nicht automatisch als belegt interpretiert.' },
          { type: 'links', items: [{ label: 'Leerstand und Belegungsstatus', to: '/dokumentation/leerstand' }] }
        ]
      },
      {
        id: 'osm-und-stadtplaner-unterschied',
        title: 'Warum unterscheiden sich OpenStreetMap und Stadtplaner?',
        blocks: [
          { type: 'paragraph', text: 'Beide Quellen werden unabhängig gepflegt und können unterschiedliche Attribute oder Aktualisierungsstände besitzen. Eine verknüpfte Stadtplaner-Fläche hat in der gemeinsamen Kartendarstellung Vorrang, damit dasselbe Objekt nicht doppelt gezählt wird.' }
        ]
      },
      {
        id: 'statistik-fehlt',
        title: 'Warum fehlt eine Statistik?',
        blocks: [
          { type: 'paragraph', text: 'Nicht für jede Kennzahl, Periode oder Gebietsebene liegt ein veröffentlichter Wert vor. Fehlende Angaben werden nicht geschätzt. Prüfen Sie Statistikgebiet, Berichtsperiode und Quelle in der Anzeige.' },
          { type: 'links', items: [{ label: 'Kommunale Statistik verstehen', to: '/dokumentation/statistik' }] }
        ]
      },
      {
        id: 'quartier-parent-wert',
        title: 'Warum zeigt ein Quartier den Wert eines Stadtteils?',
        blocks: [
          { type: 'paragraph', text: 'Für Quartiere liegen derzeit keine künstlich verteilten eigenen Statistikwerte vor. Deshalb kann der Stadtplaner den veröffentlichten Wert des übergeordneten Stadtteils zeigen und kennzeichnet das tatsächlich verwendete Statistikgebiet.' }
        ]
      },
      {
        id: 'konto-erforderlich',
        title: 'Brauche ich ein Konto?',
        blocks: [
          { type: 'paragraph', text: 'Nein. Karte, öffentliche Flächen- und Gebietsseiten, Kennzahlen und Dokumentation sind ohne Anmeldung lesbar. Ein Konto wird für persönliche Funktionen und das Anlegen eigener Flächen benötigt; Änderungen setzen zusätzliche Berechtigungen voraus.' }
        ]
      },
      {
        id: 'intelligente-suche',
        title: 'Was kann die intelligente Suche?',
        blocks: [
          { type: 'paragraph', text: 'Sie versteht ausgewählte Kartenbefehle, Filter, Statistikfragen und Begriffserklärungen. Sie verändert keine Daten und schätzt keine fehlenden Zahlen.' },
          { type: 'links', items: [{ label: 'Intelligente Suche verwenden', to: '/dokumentation/suche' }] }
        ]
      },
      {
        id: 'daten-korrigieren',
        title: 'Daten fehlen oder sind falsch – was kann ich tun?',
        blocks: [
          { type: 'table', headers: ['Betroffene Angabe', 'Passender Weg'], rows: [['OpenStreetMap-Objekt oder Gebäude', 'Über den angebotenen Link mit StreetComplete oder dem OpenStreetMap-Editor verbessern.'], ['Stadtplaner-Fläche', 'Bei vorhandener Berechtigung auf der Detailseite bearbeiten oder über die Kontaktseite melden.'], ['Kommunale Statistik', 'Quelle und Berichtsperiode prüfen; der Stadtplaner übernimmt nur veröffentlichte Werte.']] },
          { type: 'links', items: [{ label: 'Kontakt aufnehmen', to: '/kontakt' }, { label: 'OpenStreetMap verbessern', to: '/dokumentation/openstreetmap#osm-daten-ergaenzen' }, { label: 'Flächen bearbeiten', to: '/dokumentation/flaechen-bearbeiten' }] }
        ]
      },
      {
        id: 'kennzahl-strich',
        title: 'Was bedeutet ein Gedankenstrich bei Kennzahlen?',
        blocks: [
          { type: 'paragraph', text: 'Für diesen Wert ist derzeit keine Zahl hinterlegt. Der Gedankenstrich ist nicht mit dem Zahlenwert null gleichzusetzen.' }
        ]
      },
      {
        id: 'weitere-hilfe',
        title: 'Wo erhalte ich weitere Hilfe?',
        blocks: [
          { type: 'links', items: [{ label: 'Kontakt', to: '/kontakt', description: 'Kontaktmöglichkeiten des OK Lab Flensburg.' }, { label: 'Über das Projekt', to: '/ueber-das-projekt', description: 'Hintergrund und Zielsetzung des Stadtplaners.' }, { label: 'Open Data', to: '/open-data', description: 'Informationen zur offenen Datennutzung.' }] }
        ]
      }
    ]
  }
]

export const documentationPaths = documentationPages.map(page => page.slug ? `/dokumentation/${page.slug}` : '/dokumentation')

export const documentationGroupOrder = [
  'Einstieg',
  'Karte und Daten',
  'Analyse',
  'Konto und Bearbeitung',
  'Hilfe',
  'Quellcode und Entwicklung'
] as const
