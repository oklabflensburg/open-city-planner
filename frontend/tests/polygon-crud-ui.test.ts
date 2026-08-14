import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import {
  fallbackIndustryColor,
  getIndustryColor,
  getIndustryLabel,
  industries,
  industryColors
} from '../app/utils/industries'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')
const serverFile = (path: string) => readFileSync(fileURLToPath(new URL(`../server/${path}`, import.meta.url)), 'utf8')

describe('polygon create and delete UI', () => {
  it('keeps account navigation free of GIS creation and restores create to the authenticated map action areas', () => {
    const header = appFile('components/layout/AppHeader.vue')
    const shell = appFile('components/layout/AppShell.vue')
    const ownPolygons = appFile('pages/meine-flaechen.vue')
    expect(header).not.toContain("{ label: 'Neue Fläche', to: '/flaechen/neu' }")
    expect(header).toContain("v-if=\"route.path === '/'\"")
    expect(header).toContain('to="/flaechen/neu"')
    expect(header).toContain('v-if="authStore.authenticated"')
    expect(shell).toContain('v-if="authStore.authenticated"')
    expect(shell).toContain('to="/flaechen/neu"')
    expect(shell).toContain('aria-label="Neue Fläche anlegen"')
    expect(ownPolygons).not.toContain('to="/flaechen/neu"')
  })

  it('protects the create page and disables creation without geometry', () => {
    const page = appFile('pages/flaechen/neu.vue')
    expect(page).toContain("definePageMeta({ middleware: 'auth' })")
    expect(page).toContain("robots: 'noindex,nofollow'")
    expect(page).toContain(':disabled="!canSubmit || submitting"')
    expect(page).toContain('!!geometry.value && !!name.value.trim()')
    expect(page).not.toContain('schedulePublic')
  })

  it('posts once and navigates to the server-generated slug', () => {
    const page = appFile('pages/flaechen/neu.vue')
    expect(page).toContain('await polygonApi.create')
    expect(page).toContain('await navigateTo(`/flaechen/${created.slug}`)')
    expect(page).toContain('if (!canSubmit.value || !geometry.value || submitting.value) return')
  })

  it('excludes the create route from the sitemap and revalidates deleted slugs', () => {
    const sitemap = serverFile('routes/sitemap.xml.ts')
    expect(sitemap).not.toContain("'/flaechen/neu'")
    expect(sitemap).toContain("'no-cache, must-revalidate'")
  })

  it('derives delete visibility from a server capability', () => {
    const permissions = appFile('composables/usePolygonPermissions.ts')
    const detail = appFile('pages/flaechen/[slug].vue')
    expect(permissions).toContain('!!editor.value?.can_delete')
    expect(detail).toContain('<PolygonDeleteSection v-if="canDelete"')
    expect(detail).toContain('await polygonApi.remove(polygonData.value.id)')
    expect(detail).toContain('clearNuxtData(`polygon-${slug}`)')
    expect(detail).toContain("await navigateTo('/')")
  })

  it('requires explicit destructive confirmation and prevents duplicate requests', () => {
    const section = appFile('components/polygon/PolygonDeleteSection.vue')
    const confirmation = appFile('components/ui/AppConfirmDialog.vue')
    expect(section).toContain('<AppConfirmDialog')
    expect(confirmation).toContain('role="alertdialog"')
    expect(section).toContain('Diese Aktion kann nicht rückgängig gemacht werden.')
    expect(confirmation).toContain("cancelLabel: 'Abbrechen'")
    expect(section).toContain('Endgültig löschen')
    expect(section).toContain(':loading="loading"')
    expect(section).toContain('loading-label="Wird gelöscht …"')
  })
})

describe('central category presentation', () => {
  it('derives every color from the single category configuration', () => {
    expect(Object.keys(industryColors)).toHaveLength(industries.length)
    for (const industry of industries) {
      expect(industryColors[industry.key]).toBe(industry.color)
      expect(getIndustryColor(industry.key)).toBe(industry.color)
      expect(getIndustryLabel(industry.key)).toBe(industry.label)
    }
  })

  it('preserves an unknown category label with a neutral fallback color', () => {
    expect(getIndustryLabel('historical-category')).toBe('historical-category')
    expect(getIndustryColor('historical-category')).toBe(fallbackIndustryColor)
  })

  it('uses category colors on overview, detail map, badge, filter and analytics', () => {
    expect(appFile('components/map/MapCanvas.vue')).toContain('industryColorExpression')
    expect(appFile('components/polygon/PolygonDetailMap.vue')).toContain("'fill-color': props.color")
    expect(appFile('components/polygon/PolygonCategoryBadge.vue')).toContain('getIndustryColor')
    expect(appFile('components/filters/IndustryFilter.vue')).toContain('industryColors[industry.key]')
    expect(appFile('components/analysis/IndustryChart.vue')).toContain('industryColors[industry.key]')
  })

  it('keeps the overview map read-only and confines drawing to the create route', () => {
    expect(appFile('components/map/MapCanvas.vue')).not.toContain('TerraDraw')
    expect(appFile('components/polygon/PolygonCreateMap.vue')).toContain('TerraDrawPolygonMode')
  })
})
