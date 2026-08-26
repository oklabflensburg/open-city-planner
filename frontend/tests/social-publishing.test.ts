import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { mapHostSource } from './map-host-source'
import { documentationPages } from '~/config/documentation'
import { projectConfig } from '~/config/project'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')

describe('Mastodon and Fediverse integration', () => {
  it('defines the official account centrally without exposing a backend token', () => {
    expect(projectConfig.social.mastodon).toEqual({
      label: 'Mastodon',
      url: 'https://norden.social/@oklabflensburg',
      handle: '@oklabflensburg@norden.social'
    })
    const frontendSources = [
      appFile('config/project.ts'),
      appFile('components/project/MastodonLink.vue'),
      appFile('pages/admin/social.vue')
    ].join('\n')
    expect(frontendSources).not.toContain('MASTODON_ACCESS_TOKEN')
    expect(frontendSources).not.toContain('access_token')
  })

  it('uses a safe identity link in the footer and project context', () => {
    const link = appFile('components/project/MastodonLink.vue')
    expect(link).toContain("identity ? 'me noopener noreferrer' : 'noopener noreferrer'")
    expect(link).toContain('target="_blank"')
    expect(link).toContain('öffnet in einem neuen Tab')
    expect(appFile('components/layout/AppFooter.vue')).toContain('<MastodonLink identity variant="footer"')
    const about = appFile('pages/ueber-das-projekt.vue')
    expect(about).toContain('<ContentSection title="Mastodon & Fediverse"')
    expect(about).toContain("sameAs: [projectConfig.social.mastodon.url")
  })

  it('documents ActivityPub delegation, coalescing, privacy and bulk policies', () => {
    const overview = documentationPages.find(page => page.slug === '')!
    const section = overview.sections.find(item => item.id === 'mastodon-und-fediverse')!
    expect(section).toBeDefined()
    expect(JSON.stringify(section)).toContain('ActivityPub-Actor')
    expect(JSON.stringify(section)).toContain('fünf Minuten')
    expect(JSON.stringify(section)).toContain('reguläre OSM-Sync erzeugt keine Posts')
    expect(JSON.stringify(section)).toContain('höchstens einen zusammenfassenden Hinweis')
    expect(JSON.stringify(section)).toContain('Eigentümer-')
  })

  it('provides a protected admin view with status, history and confirmed retry', () => {
    const page = appFile('pages/admin/social.vue')
    const composable = appFile('composables/useSocialPublishing.ts')
    expect(page).toContain("definePageMeta({ middleware: 'social-publish' })")
    expect(page).toContain('Publication History')
    expect(page).toContain('Automatisch veröffentlichte Themen')
    expect(page).toContain('Screenshot-Einstellungen')
    expect(page).toContain('Neue aus OSM übernommene Flächen')
    expect(page).toContain("toggleEvent('POLYGON_ADOPTED_FROM_OSM')")
    expect(page).toContain('polygon_osm_adoption_link_target')
    expect(page).toContain("item.resource_type === 'USER_POLYGON'")
    expect(page).toContain('Mastodon Vorschau')
    expect(page).toContain('<AppConfirmDialog')
    expect(page).not.toContain('confirm(')
    expect(page).not.toContain('Einstellungen speichern')
    expect(page).toContain('Änderungen werden automatisch gespeichert.')
    expect(page).toContain('aria-live="polite"')
    expect(page).toContain('TEXT_SAVE_DELAY_MS = 600')
    expect(page).toContain('CONTROL_SAVE_DELAY_MS = 100')
    expect(page).toContain('onBeforeRouteLeave')
    expect(composable).toContain("'/admin/social/mastodon/status'")
    expect(composable).toContain('/admin/social/publications')
    expect(composable).toContain("'/admin/social/settings'")
    expect(composable).toContain('createSerialSaveQueue')
    expect(composable).toContain('saveSettingsPatch')
    expect(composable).not.toContain('await load()\n    } finally { savingSettings')
    expect(composable).toContain("'approve-and-publish' | 'cancel'")
    expect(page).toContain('Freigeben & veröffentlichen')
    expect(page).toContain("allows(item, 'APPROVE_AND_PUBLISH')")
    expect(appFile('components/layout/AppHeader.vue')).toContain("{ label: 'Social Publishing', to: '/admin/social' }")
  })

  it('documents automatic persistence for social settings', () => {
    const administration = documentationPages.find(page => page.slug === 'administration')!
    const section = administration.sections.find(item => item.id === 'social-publishing')!
    expect(JSON.stringify(section)).toContain('automatisch gespeichert')
  })

  it('provides a public noindex screenshot-ready mode for allowlisted area pages', () => {
    const areaPage = appFile('pages/gebiete/[slug].vue')
    const map = appFile('components/analysis/AnalysisAreaDetailMap.vue')
    expect(areaPage).toContain('data-social-preview-capture')
    expect(areaPage).toContain('data-social-preview-ready')
    expect(areaPage).toContain("robots: 'noindex,nofollow'")
    expect(map).toContain("emit('ready')")
  })

  it('provides anonymous screenshot-ready modes for polygon detail and GIS targets', () => {
    const detail = appFile('pages/flaechen/[slug].vue')
    const shell = appFile('components/layout/AppShell.vue')
    const map = mapHostSource()
    expect(detail).toContain('data-social-preview-capture')
    expect(detail).toContain('data-social-preview-ready')
    expect(detail).toContain("robots: 'noindex,nofollow'")
    expect(shell).toContain('data-social-preview-capture')
    expect(map).toContain('gisPreviewReady')
    expect(map).toContain("instance.once('moveend'")
    expect(map).toContain("route.query.polygon")
    expect(map).toContain('await selectPolygon(requested, true)')
  })
})
