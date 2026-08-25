import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { useSiteNavigation } from '~/composables/useSiteNavigation'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')

describe('site navigation', () => {
  it('uses the logo as home link and omits the redundant Start item', () => {
    const { primaryNavigation } = useSiteNavigation()

    expect(primaryNavigation).toEqual([
      { label: 'Karte', to: '/karte' },
      { label: 'Gebiete', to: '/gebiete' },
      { label: 'Über das Projekt', to: '/ueber-das-projekt' },
      { label: 'Dokumentation', to: '/dokumentation' }
    ])

    const header = appFile('components/layout/AppHeader.vue')
    expect(header).toContain('<NuxtLink class="group flex min-h-11 shrink-0 items-center rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#154d73]" to="/"')
    expect(header).toContain('v-for="item in primaryNavigation"')
    expect(header).toContain(':primary-navigation="primaryNavigation"')
    expect(appFile('components/layout/MobileNavigation.vue')).toContain('v-for="item in primaryNavigation"')
  })
})
