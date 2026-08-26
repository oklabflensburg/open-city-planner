import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { composeNavigation, hostPrimaryNavigation } from '~/composables/useSiteNavigation'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')

describe('site navigation', () => {
  it('uses the logo as home link and omits the redundant Start item', () => {
    const primaryNavigation = composeNavigation(hostPrimaryNavigation)

    expect(primaryNavigation).toEqual([
      expect.objectContaining({ label: 'Karte', to: '/karte' }),
      expect.objectContaining({ label: 'Über das Projekt', to: '/ueber-das-projekt' }),
      expect.objectContaining({ label: 'Dokumentation', to: '/dokumentation' })
    ])
    expect(hostPrimaryNavigation.some(item => item.to === '/gebiete')).toBe(false)
    const areaModule = JSON.parse(readFileSync(fileURLToPath(new URL('../frontend-modules/analysis-areas/module.json', import.meta.url)), 'utf8'))
    expect(areaModule.publicContributions.ui).toContainEqual(expect.objectContaining({
      id: 'analysis-areas.primary-navigation', label: 'Gebiete', to: '/gebiete'
    }))

    const header = appFile('components/layout/AppHeader.vue')
    expect(header).toContain('<NuxtLink class="group flex min-h-11 shrink-0 items-center rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#154d73]" to="/"')
    expect(header).toContain('v-for="item in primaryNavigation"')
    expect(header).toContain(':primary-navigation="primaryNavigation"')
    const mobile = appFile('components/layout/MobileNavigation.vue')
    expect(mobile).toContain('aria-label="Mobile Navigation"')
    expect(mobile).toContain('v-for="item in primaryNavigation"')
    expect(mobile).toContain(':aria-current="isActive(item) ? \'page\' : undefined"')
    expect(mobile).toContain('@click="$emit(\'close\')"')
    expect(mobile).toContain('focus-visible:outline')
  })
})
