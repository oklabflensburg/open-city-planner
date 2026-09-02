import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const root = resolve(import.meta.dirname, '..')
const removedPaths = [
  'app/components/search/IntelligentSearch.vue',
  'app/pages/admin/social.vue',
  'app/pages/vergleich.vue',
  'app/stores/analytics.ts',
  'app/stores/comparison.ts',
  'app/stores/search.ts',
  'frontend-modules/analysis-areas/module.json'
]
const forbiddenRuntimeTokens = [
  '/api/v1/analysis-areas',
  '/api/v1/analytics',
  '/api/v1/assistant',
  '/api/v1/search',
  '/admin/social',
  '/gebiete',
  '/vergleich',
  'analysis-areas.',
  'AssistantPanel',
  'social-preview',
  'useAnalyticsStore',
  'IntelligentSearch',
  'ComparableList',
  'LocationAnalysis'
]

function runtimeSources() {
  const glob = import.meta.glob('../app/**/*.{ts,vue}', { query: '?raw', import: 'default', eager: true })
  return Object.entries(glob) as Array<[string, string]>
}

describe('slim Host frontend boundary', () => {
  it('keeps removed domain entrypoints absent', () => {
    expect(removedPaths.filter(path => existsSync(resolve(root, path)))).toEqual([])
  })

  it('blocks removed domain routes and stores from runtime source', () => {
    const violations = runtimeSources().flatMap(([path, source]) =>
      forbiddenRuntimeTokens.filter(token => source.includes(token)).map(token => `${path}: ${token}`)
    )
    expect(violations).toEqual([])
  })

  it('retains notifications and generic map contribution slots', () => {
    expect(readFileSync(resolve(root, 'app/stores/notifications.ts'), 'utf8')).toContain('fetchNotifications')
    expect(readFileSync(resolve(root, 'app/components/map/MapCanvas.vue'), 'utf8')).toContain('UiContributionSlot')
  })
})
