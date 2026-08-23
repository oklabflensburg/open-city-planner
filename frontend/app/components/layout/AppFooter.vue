<template>
  <footer class="w-full border-t border-[var(--c-primary-800)] bg-[var(--c-primary-900)] text-[#eef7f8]">
    <div class="mx-auto w-full max-w-[1920px] px-4 py-10 sm:px-6 lg:px-8 xl:px-10 2xl:px-12">
      <div class="grid gap-8 md:grid-cols-2 lg:grid-cols-12 lg:gap-10">
        <section class="lg:col-span-5">
          <div class="flex max-w-md flex-col gap-4 sm:flex-row sm:items-center">
            <div class="w-fit rounded-xl bg-white p-2">
              <OKLabLogo size="footer" />
            </div>
            <div>
              <h2 class="text-base font-semibold text-white">OK Lab Flensburg</h2>
              <p class="mt-2 max-w-sm text-sm leading-relaxed text-slate-400">
                Offene Daten, offene Technologien und digitale Werkzeuge für Flensburg.
              </p>
            </div>
          </div>
        </section>

        <nav aria-label="Projekt" class="grid content-start gap-3 lg:col-span-2">
          <h2 class="text-xs font-semibold uppercase tracking-wider text-slate-400">Projekt</h2>
          <NuxtLink v-for="item in primaryNavigation" :key="item.to" class="text-sm font-medium text-slate-300 transition hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#9ed0dd]" :to="item.to">
            {{ item.label }}
          </NuxtLink>
        </nav>

        <nav aria-label="Rechtliches" class="grid content-start gap-3 lg:col-span-2">
          <h2 class="text-xs font-semibold uppercase tracking-wider text-slate-400">Rechtliches</h2>
          <NuxtLink v-for="item in legalNavigation" :key="item.to" class="text-sm font-medium text-slate-300 transition hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#9ed0dd]" :to="item.to">
            {{ item.label }}
          </NuxtLink>
          <a
            class="text-sm font-medium text-slate-300 transition hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#9ed0dd]"
            :href="licenseUrl"
            target="_blank"
            rel="noopener noreferrer"
          >
            Quellcode · AGPL-3.0
          </a>
        </nav>

        <nav aria-label="Weitere Links" class="grid content-start gap-3 lg:col-span-3">
          <h2 class="text-xs font-semibold uppercase tracking-wider text-slate-400">Links</h2>
          <NuxtLink v-for="item in additionalNavigation" :key="item.to" class="text-sm font-medium text-slate-300 transition hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#9ed0dd]" :to="item.to">
            {{ item.label }}
          </NuxtLink>
          <GitHubLink variant="footer" />
          <MastodonLink identity variant="footer" />
        </nav>
      </div>

      <div class="mt-8 flex flex-col gap-2 border-t border-white/10 pt-5 text-xs font-semibold text-slate-400 md:flex-row md:items-center md:justify-between">
        <span>© {{ currentYear }} OK Lab Flensburg</span>
        <span>Open Data · Civic Tech · AGPL-3.0</span>
      </div>
    </div>
  </footer>
</template>

<script setup lang="ts">
import { projectConfig } from '~/config/project'

const { primaryNavigation, legalNavigation } = useSiteNavigation()
const currentYear = new Date().getFullYear()
const licenseUrl = `${projectConfig.github.url}/blob/main/LICENSE`
const additionalNavigation = [
  { label: 'Open Data', to: '/open-data' },
  { label: 'Kontakt', to: '/kontakt' }
]
</script>
