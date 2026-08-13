<template>
  <LegalPageLayout title="Datenschutzerklärung" intro="Technische Datenschutzhinweise zur Open City Map.">
    <section>
      <h2 class="text-base font-bold text-[#202427]">Verantwortliche Stelle</h2>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Verantwortliche Stelle für die Verarbeitung personenbezogener Daten ist:
      </p>
      <address class="mt-3 not-italic text-sm leading-7 text-[#4f575c]">
        {{ addressName }}<br>
        {{ addressStreet }} {{ addressHouseNumber }}<br>
        {{ addressPostalCode }} {{ addressCity }}<br>
        Deutschland
      </address>
      <p v-if="contactMail" class="mt-3 text-sm leading-6 text-[#4f575c]">
        E-Mail:
        <a class="text-[#154d73] underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]" :href="`mailto:${contactMail}`">{{ contactMail }}</a>
      </p>
      <p v-if="contactPhone" class="mt-1 text-sm leading-6 text-[#4f575c]">
        Telefon:
        <a class="text-[#154d73] underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]" :href="`tel:${contactPhone}`">{{ contactPhone }}</a>
      </p>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Die konkrete datenschutzrechtlich verantwortliche Person ist nicht hartcodiert. Falls erforderlich, muss sie über <code class="rounded bg-[#eef2f3] px-1 py-0.5">NUXT_PUBLIC_PRIVACY_CONTACT_PERSON</code> gesetzt und rechtlich geprüft werden.
      </p>
    </section>

    <section>
      <h2 class="text-base font-bold text-[#202427]">Verwaltungsinterne Eigentümerdaten</h2>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Zu einer Fläche können fachlicher Eigentümer, Eigentümeranschrift und Quadratmeterpreis verwaltungsintern gespeichert werden. Diese Daten werden vom Backend ausschließlich Konten mit der Rolle <code class="rounded bg-[#eef2f3] px-1 py-0.5">VERWALTUNG</code> bereitgestellt. Sie erscheinen nicht in öffentlichen Flächendetails, Suchmaschinen-Metadaten, strukturierten Daten oder der Sitemap.
      </p>
    </section>

    <section>
      <h2 class="text-base font-bold text-[#202427]">Automatische Adressauflösung</h2>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Nach dem Speichern einer Polygongeometrie kann das Backend einen innerhalb der Fläche liegenden Punkt an den vom Betreiber konfigurierten Nominatim-Dienst senden, um die öffentliche Lageadresse zu bestimmen. Der konkrete Dienst wird über die Backend-Konfiguration festgelegt; ohne konfigurierte Basis-URL findet keine Übermittlung statt. Der Browser kontaktiert Nominatim nicht direkt.
      </p>
    </section>

    <section>
      <h2 class="text-base font-bold text-[#202427]">Umfang und Zweck der Verarbeitung</h2>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Die Website stellt eine interaktive GIS-Anwendung bereit. Zur Bereitstellung der Website, der Karte und der API-Funktionen können technische Zugriffsdaten verarbeitet werden, insbesondere IP-Adresse, Zeitpunkt, angefragte URL, HTTP-Status, Browser- und Betriebssysteminformationen sowie übertragene Datenmengen.
      </p>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Für lesende Nutzung der Karte ist kein Benutzerkonto erforderlich. Wenn Nutzerinnen oder Nutzer Flächen zeichnen, bearbeiten oder löschen möchten, wird ein Konto benötigt. Bei der Registrierung und Kontonutzung werden E-Mail-Adresse, Vorname, Nachname, optionaler Anzeigename, Verifikationsstatus, Zeitpunkte der Registrierung und Anmeldung sowie technische Sitzungsdaten verarbeitet.
      </p>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Beim Zeichnen, Bearbeiten und Löschen von Flächen werden Polygongeometrien, Kategorien und Eigenschaften wie Größe oder Etage an das FastAPI-Backend übertragen und in PostgreSQL/PostGIS gespeichert. Neu erstellte Flächen werden dem angemeldeten Benutzerkonto serverseitig zugeordnet, damit Bearbeitungs- und Löschrechte geprüft werden können.
      </p>
    </section>

    <section>
      <h2 class="text-base font-bold text-[#202427]">Kartenanzeige mit MapLibre und VersaTiles</h2>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Die Karte wird im Browser mit MapLibre GL gerendert. Die Standardkonfiguration lädt das Style-JSON von <code class="rounded bg-[#eef2f3] px-1 py-0.5">https://tiles.versatiles.org/assets/styles/colorful/style.json</code>.
      </p>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Die Style-Datei verweist auf Vector Tiles unter <code class="rounded bg-[#eef2f3] px-1 py-0.5">https://tiles.versatiles.org/tiles/osm/&#123;z&#125;/&#123;x&#125;/&#123;y&#125;</code>, Glyphs unter <code class="rounded bg-[#eef2f3] px-1 py-0.5">https://tiles.versatiles.org/assets/glyphs/...</code> und Sprites unter <code class="rounded bg-[#eef2f3] px-1 py-0.5">https://tiles.versatiles.org/assets/sprites/...</code>. Diese Requests werden direkt vom Browser an den konfigurierten VersaTiles-Server ausgelöst. Dabei können IP-Adresse, User-Agent, Zeitpunkt und angefragte Kartenressourcen beim Tile-Server verarbeitet werden. Die Kartenbasis enthält OpenStreetMap-Daten und wird entsprechend attribuiert.
      </p>
    </section>

    <section>
      <h2 class="text-base font-bold text-[#202427]">FastAPI, PostgreSQL und PostGIS</h2>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Das Frontend kommuniziert über die konfigurierte API-Basis-URL mit einem FastAPI-Backend. Die API speichert Benutzerkonten, serverseitige Refresh-Sessions, E-Mail-Verifikations- und Passwort-Reset-Token sowie Polygonobjekte und Geometrien in PostgreSQL/PostGIS. Passwörter werden nicht im Klartext gespeichert, sondern mit Argon2id gehasht. Reset-, Verifikations- und Refresh-Tokens werden serverseitig nur gehasht gespeichert.
      </p>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Beim Auswählen einer Fläche lädt das Backend passende, öffentliche OpenStreetMap-Sachdaten bevorzugt aus der lokalen PostGIS-Datenbank. Nur wenn dort kein Treffer vorliegt und der Betreiber ausdrücklich einen externen Overpass-Dienst konfiguriert hat, kann die Polygongeometrie serverseitig an diesen Dienst übermittelt werden. Der Browser kontaktiert keine Overpass-Schnittstelle direkt.
      </p>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Serverseitige Logs können beim Frontend-Hosting, beim API-Server und bei der Datenbank-Infrastruktur entstehen. Bei Auth-Sessions können IP-Adresse und User-Agent gespeichert werden, um Sitzungen zu verwalten und Missbrauch zu erschweren. Hosting-Anbieter, Serverstandorte und Log-Aufbewahrungsfristen sind im Repository nicht festgelegt und müssen vom Betreiber dokumentiert werden.
      </p>
    </section>

    <section>
      <h2 class="text-base font-bold text-[#202427]">Registrierung, Anmeldung und E-Mail-Versand</h2>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Für Registrierung, Login, E-Mail-Verifikation, Passwort-Reset, Passwortänderung und Profilbearbeitung werden die dafür erforderlichen Kontodaten verarbeitet. Die Authentifizierung erfolgt über HttpOnly-Cookies für Access- und Refresh-Tokens sowie ein separates CSRF-Token für schreibende Anfragen. JWTs werden nicht im <code class="rounded bg-[#eef2f3] px-1 py-0.5">localStorage</code> gespeichert.
      </p>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Nutzerinnen und Nutzer können freiwillig ein Profilbild hochladen. Das Bild wird serverseitig geprüft, zugeschnitten, verkleinert, in WebP umgewandelt und ohne EXIF-Metadaten als Datei gespeichert. In der Datenbank wird nur die URL zum Profilbild am Benutzerkonto hinterlegt. Die Profilbild-Datei kann über diese URL im Browser geladen werden, solange sie im Konto verwendet wird.
      </p>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        E-Mails zur Bestätigung der E-Mail-Adresse, zum Passwort-Reset und als Sicherheitshinweis werden serverseitig erzeugt. Im Entwicklungsmodus werden E-Mails in der Backend-Konsole ausgegeben. Im Produktivbetrieb hängt der konkrete E-Mail-Dienstleister von der SMTP-Konfiguration des Betreibers ab und muss dort ergänzt werden.
      </p>
    </section>

    <section>
      <h2 class="text-base font-bold text-[#202427]">Optionale OAuth-Anmeldung</h2>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Die Anwendung besitzt eine vorbereitete Architektur für externe OAuth- beziehungsweise OpenID-Connect-Anmeldungen. Solche Provider werden nur aktiviert, wenn der Betreiber die zugehörigen Umgebungsvariablen vollständig konfiguriert. Nicht konfigurierte Provider werden nicht in der Oberfläche angezeigt und hier nicht als eingesetzter Dienst benannt.
      </p>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Bei Anmeldung oder Kontoverknüpfung über einen externen Anbieter werden zur Zuordnung des lokalen Benutzerkontos insbesondere die vom Anbieter übermittelte eindeutige Benutzerkennung sowie, abhängig vom Anbieter, E-Mail-Adresse, Benutzername, Anzeigename und Profilbild-URL verarbeitet. OAuth-Zugriffs-, Refresh- oder ID-Tokens werden nicht dauerhaft in der Tabelle für verknüpfte Konten gespeichert.
      </p>
    </section>

    <section>
      <h2 class="text-base font-bold text-[#202427]">Rechtsgrundlagen</h2>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Die Verarbeitung technischer Zugriffsdaten kann auf Art. 6 Abs. 1 lit. f DSGVO beruhen, soweit sie zur Bereitstellung, Stabilität und Sicherheit der Website erforderlich ist. Kommunikationsdaten bei Kontaktaufnahme können je nach Kontext auf Art. 6 Abs. 1 lit. b oder lit. f DSGVO beruhen. Konkrete Rechtsgrundlagen für den Produktivbetrieb müssen vom Betreiber geprüft werden.
      </p>
    </section>

    <section>
      <h2 class="text-base font-bold text-[#202427]">Empfänger und Drittlandübermittlung</h2>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Zugriff auf Daten können technische Dienstleister erhalten, die Frontend, API, Datenbank oder Kartenressourcen bereitstellen. Im aktuellen Repository sind keine konkreten Hosting-Anbieter hinterlegt. Drittlandübermittlungen sind im Code nicht erkennbar; sie hängen vom tatsächlichen Hosting und von der produktiven Karten-/Tile-Konfiguration ab.
      </p>
    </section>

    <section>
      <h2 class="text-base font-bold text-[#202427]">Cookies, LocalStorage und externe Medien</h2>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Für angemeldete Nutzerinnen und Nutzer setzt das Backend Auth-Cookies. Access- und Refresh-Token-Cookies sind für JavaScript nicht lesbar. Das CSRF-Cookie ist lesbar, damit der Browser bei schreibenden Anfragen den Double-Submit-Schutz bedienen kann. Im Frontend werden keine JWTs in <code class="rounded bg-[#eef2f3] px-1 py-0.5">localStorage</code> oder <code class="rounded bg-[#eef2f3] px-1 py-0.5">sessionStorage</code> gespeichert. Es wurden keine Nutzungsanalyse-Integration, keine Fehlertracking-Integration und keine externen Video-Einbettungen gefunden. Es werden keine externen Webfonts geladen; die Anwendung nutzt Systemschriftarten.
      </p>
    </section>

    <section>
      <h2 class="text-base font-bold text-[#202427]">Speicherdauer</h2>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Polygon- und Geometriedaten bleiben gespeichert, bis sie über die Anwendung gelöscht oder vom Betreiber entfernt werden. E-Mail-Verifikations- und Passwort-Reset-Token besitzen technische Ablaufzeiten und sind nur einmal verwendbar. Refresh-Sessions laufen nach der konfigurierten Dauer ab oder werden durch Logout, Logout auf allen Geräten oder Passwortreset widerrufen. Wird ein Profilbild ersetzt oder entfernt, wird die Verknüpfung am Konto gelöscht und die bisherige lokale Avatar-Datei entfernt. Konkrete Löschfristen für Server-Logs und Backups sind im Repository nicht festgelegt und müssen vom Betreiber ergänzt werden.
      </p>
    </section>

    <section>
      <h2 class="text-base font-bold text-[#202427]">Ihre Rechte</h2>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Sie können Rechte nach der DSGVO geltend machen, insbesondere Auskunft nach Art. 15 DSGVO, Berichtigung nach Art. 16 DSGVO, Löschung nach Art. 17 DSGVO, Einschränkung der Verarbeitung nach Art. 18 DSGVO, Datenübertragbarkeit nach Art. 20 DSGVO und Widerspruch nach Art. 21 DSGVO. Eine erteilte Einwilligung kann mit Wirkung für die Zukunft widerrufen werden. Außerdem besteht ein Beschwerderecht bei einer Datenschutz-Aufsichtsbehörde.
      </p>
    </section>

    <section>
      <h2 class="text-base font-bold text-[#202427]">Automatisierte Entscheidungsfindung</h2>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Im aktuellen Projekt gibt es keine automatisierte Entscheidungsfindung einschließlich Profiling, die rechtliche Wirkung gegenüber Nutzerinnen oder Nutzern entfaltet.
      </p>
    </section>
  </LegalPageLayout>
</template>

<script setup lang="ts">
const {
  contactMail,
  contactPhone,
  addressName,
  addressStreet,
  addressHouseNumber,
  addressPostalCode,
  addressCity
} = usePublicContact()

usePageSeo({
  title: 'Datenschutzerklärung',
  description: 'Datenschutzerklärung zur Open City Map mit MapLibre, VersaTiles, FastAPI und PostGIS.',
  path: '/datenschutz',
  robots: 'noindex,follow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
