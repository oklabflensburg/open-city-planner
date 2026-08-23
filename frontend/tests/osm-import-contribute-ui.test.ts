import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { getOsmIdEditorUrl, getOsmObjectUrl, getStreetCompleteUrl } from '../app/utils/osmLinks'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')

describe('OSM import and contribution journeys', () => {
  it('builds safe node, way and relation URLs centrally', () => {
    expect(getOsmObjectUrl('node', 1)).toBe('https://www.openstreetmap.org/node/1')
    expect(getOsmObjectUrl('way', 2)).toBe('https://www.openstreetmap.org/way/2')
    expect(getOsmObjectUrl('relation', 3)).toBe('https://www.openstreetmap.org/relation/3')
    expect(getOsmObjectUrl('invalid', 3)).toBeNull()
  })

  it('centres iD on the representative point and uses the official StreetComplete site', () => {
    expect(getOsmIdEditorUrl({ latitude: 54.78, longitude: 9.43, zoom: 19 }))
      .toBe('https://www.openstreetmap.org/edit?editor=id#map=19/54.780000/9.430000')
    expect(getStreetCompleteUrl()).toBe('https://streetcomplete.app/')
  })

  it('offers contribution tools publicly without embedded editors or native dialogs', () => {
    const dialog = appFile('components/osm/OsmContributeDialog.vue')
    expect(dialog).toContain('<AppModal')
    expect(dialog).toContain('Mit iD bearbeiten')
    expect(dialog).toContain('StreetComplete')
    expect(dialog).toContain('target="_blank"')
    expect(dialog).toContain('rel="noopener noreferrer"')
    expect(dialog).not.toContain('<iframe')
    expect(dialog).not.toMatch(/alert\(|confirm\(|prompt\(/)
  })

  it('shows the Stadtplaner import action only for authenticated users', () => {
    const preview = appFile('components/osm/OsmFeatureSidebar.vue')
    expect(preview).toContain('v-if="auth.authenticated"')
    expect(preview).toContain('Als Fläche übernehmen')
    expect(preview).toContain('Weitere Fläche anlegen')
    expect(preview).toContain('<OsmContributeAction')
  })

  it('uses the central API client and handles point-without-area drawing', () => {
    const composable = appFile('composables/useOsmImport.ts')
    const dialog = appFile('components/osm/OsmImportDialog.vue')
    const createPage = appFile('pages/flaechen/neu.vue')
    expect(composable).toContain("'/polygons/from-osm'")
    expect(dialog).toContain("cause.code === 'OSM_GEOMETRY_REQUIRED'")
    expect(createPage).toContain('ein automatisch erzeugter Punkt-Buffer wird nicht gespeichert')
    expect(createPage).toContain('geometry: geometry.value')
  })

  it('renders the import confirmation in the fixed modal footer and preserves every outcome', () => {
    const dialog = appFile('components/osm/OsmImportDialog.vue')
    expect(dialog).toContain('<template #footer>')
    expect(dialog).toContain('Abbrechen')
    expect(dialog).toContain("'Fläche übernehmen'")
    expect(dialog).toContain("'Wird übernommen …'")
    expect(dialog).toContain('@click="confirmImport"')
    expect(dialog).toContain('if (importing.value) return')
    expect(dialog).toContain("cause.code === 'OSM_GEOMETRY_REQUIRED'")
    expect(dialog).toContain("cause.code === 'OSM_FEATURE_ALREADY_IMPORTED'")
    expect(dialog).toContain("emit('update:open', false)")
    expect(dialog).toContain("navigateTo(`/flaechen/${created.slug}`)")
  })

  it('keeps linked Stadtplaner areas visible and OSM references read-only', () => {
    const preview = appFile('components/osm/OsmFeatureSidebar.vue')
    const detail = appFile('pages/flaechen/[slug].vue')
    expect(preview).toContain('Bereits im Stadtplaner')
    expect(detail).toContain('Datenherkunft')
    expect(detail).toContain('polygonData.osm_sources')
    expect(detail).toContain('Auf OpenStreetMap ansehen')
    expect(appFile('components/polygon/PolygonManagementForm.vue')).toContain('Initial aus OpenStreetMap übernommen')
  })

  it('keeps mobile actions touch sized', () => {
    const dialog = appFile('components/osm/OsmContributeDialog.vue')
    const preview = appFile('components/osm/OsmFeatureSidebar.vue')
    expect(dialog).toContain('min-h-11')
    expect(preview).toContain('page-button-primary')
  })
})
