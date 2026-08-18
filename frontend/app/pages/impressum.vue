<template>
  <LegalPageLayout title="Impressum" intro="Angaben zum Anbieter von Stadtplaner.">
    <section>
      <h2 class="text-base font-bold text-[#202427]">Angaben nach DDG</h2>
      <address class="mt-3 not-italic text-sm leading-7 text-[#4f575c]">
        {{ addressName }}<br>
        {{ addressStreet }} {{ addressHouseNumber }}<br>
        {{ addressPostalCode }} {{ addressCity }}<br>
        Deutschland
      </address>
      <dl class="mt-5 grid gap-3 text-sm leading-6 text-[#4f575c]">
        <div v-if="contactMail">
          <dt class="font-bold text-[#202427]">E-Mail</dt>
          <dd>
            <a class="text-[#154d73] underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]" :href="`mailto:${contactMail}`">
              {{ contactMail }}
            </a>
          </dd>
        </div>
        <div v-if="contactPhone">
          <dt class="font-bold text-[#202427]">Telefon</dt>
          <dd>
            <a class="text-[#154d73] underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#154d73]" :href="`tel:${contactPhone}`">
              {{ contactPhone }}
            </a>
          </dd>
        </div>
      </dl>
    </section>

    <section>
      <h2 class="text-base font-bold text-[#202427]">Inhaltlich verantwortlich</h2>
      <p v-if="privacyContactPerson" class="mt-3 text-sm leading-6 text-[#4f575c]">
        Inhaltlich verantwortlich nach § 18 Abs. 2 MStV ist {{ privacyContactPerson }}.
      </p>
      <p v-else class="mt-3 text-sm leading-6 text-[#4f575c]">
        Die nach § 18 Abs. 2 MStV verantwortliche Person ist im aktuellen Projekt noch nicht per Runtime Config gesetzt und muss vom Betreiber geprüft und ergänzt werden.
      </p>
    </section>

    <section>
      <h2 class="text-base font-bold text-[#202427]">Haftung für Inhalte</h2>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Die Inhalte dieser Seiten wurden mit Sorgfalt erstellt. Für Richtigkeit, Vollständigkeit und Aktualität kann jedoch keine Gewähr übernommen werden. Als Diensteanbieter ist der Betreiber für eigene Inhalte nach den allgemeinen Gesetzen verantwortlich. Verpflichtungen zur Entfernung oder Sperrung der Nutzung von Informationen nach den allgemeinen Gesetzen bleiben unberührt.
      </p>
    </section>

    <section>
      <h2 class="text-base font-bold text-[#202427]">Haftung für Links</h2>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Diese Anwendung kann Links zu externen Webseiten Dritter enthalten, auf deren Inhalte kein Einfluss besteht. Für diese Inhalte ist stets der jeweilige Anbieter oder Betreiber der verlinkten Seiten verantwortlich. Bei Bekanntwerden von Rechtsverletzungen werden entsprechende Links entfernt.
      </p>
    </section>

    <section>
      <h2 class="text-base font-bold text-[#202427]">Urheberrecht</h2>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Die durch den Betreiber erstellten Inhalte und Werke unterliegen dem deutschen Urheberrecht, sofern sie nicht ausdrücklich unter einer offenen Lizenz veröffentlicht wurden. Inhalte Dritter werden als solche gekennzeichnet. Hinweise auf mögliche Rechtsverletzungen werden geprüft.
      </p>
    </section>

    <section>
      <h2 class="text-base font-bold text-[#202427]">Betreiberprüfung</h2>
      <p class="mt-3 text-sm leading-6 text-[#4f575c]">
        Die offiziellen Kontaktdaten wurden aus dem OK-Lab-Flensburg-Referenzprojekt übernommen. Vor Veröffentlichung müssen Verantwortlichkeit nach MStV, Rechtsform, Anbieterkennzeichnung nach DDG und weitere projektspezifische Pflichtangaben geprüft werden.
      </p>
    </section>
  </LegalPageLayout>
</template>

<script setup lang="ts">
const {
  contactMail,
  contactPhone,
  privacyContactPerson,
  addressName,
  addressStreet,
  addressHouseNumber,
  addressPostalCode,
  addressCity
} = usePublicContact()

usePageSeo({
  title: 'Impressum',
  description: 'Impressum und Anbieterangaben von Stadtplaner des OK Lab Flensburg.',
  path: '/impressum',
  robots: 'noindex,follow',
  openGraph: false,
  twitter: false,
  structuredData: false
})
</script>
