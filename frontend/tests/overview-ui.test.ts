import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')

describe('read-only overview UI', () => {
  it('loads the detail polygon by slug and keeps the map independent from edit permissions', () => {
    const detailPage = appFile('pages/flaechen/[slug].vue')
    expect(detailPage).toContain('polygonApi.bySlug(slug)')
    expect(detailPage).toContain(':geometry="polygonData.geometry"')
    expect(detailPage).toContain(':bbox="polygonData.bbox"')
    expect(detailPage).toContain(':editable="canEditPublicFields"')
    expect(detailPage).toContain('@geometry-complete="saveGeometry"')
    expect(detailPage).toContain('autosave.schedulePublic({ geometry }, true)')
    expect(detailPage).not.toContain('v-if="canEditPublicFields"\n      <PolygonDetailMap')
  })

  it('allows category labels to wrap without truncation', () => {
    const toggle = appFile('components/filters/IndustryToggle.vue')
    expect(toggle).toContain('whitespace-normal')
    expect(toggle).toContain('[overflow-wrap:anywhere]')
    expect(toggle).not.toContain('truncate')
  })

  it('does not initialize drawing or editing tools on the overview map', () => {
    const map = appFile('components/map/MapCanvas.vue')
    expect(map).not.toContain('terra-draw')
    expect(map).not.toContain('DrawingToolbar')
    expect(map).not.toContain('deletePolygon')
    expect(map).not.toContain('createPolygon')
  })

  it('links a selected polygon by slug and offers no edit controls', () => {
    const preview = appFile('components/analysis/PolygonStatistics.vue')
    expect(preview).toContain('/flaechen/${polygon.slug}')
    expect(preview).not.toContain('Bearbeiten')
    expect(preview).not.toContain('Löschen')
    expect(preview).not.toContain('Speichern')
  })

  it('registers polygon editing mode and uses a valid Terra Draw feature id', () => {
    const detailMap = appFile('components/polygon/PolygonDetailMap.vue')
    expect(detailMap).toContain('new terraDraw.TerraDrawPolygonMode()')
    expect(detailMap).toContain('terra.getFeatureId()')
    expect(detailMap).toContain('ResizeObserver')
    expect(detailMap).toContain('sm:h-[480px]')
    expect(detailMap).not.toContain("const featureId = 'detail-polygon-editor'")
    expect(detailMap).toContain('disposed || !container.isConnected')
    expect(detailMap).toContain("instance.on('webglcontextlost'")
  })

  it('does not create a late overview map after its component was disposed', () => {
    const map = appFile('components/map/MapCanvas.vue')
    expect(map).toContain('disposed || !container?.isConnected')
    expect(map).toContain('disposed = true')
    expect(map).toContain("instance.on('webglcontextrestored'")
  })

  it('does not globally override the explicit detail-map height', () => {
    const css = appFile('assets/css/main.css')
    const mapRule = css.match(/\.maplibregl-map\s*\{([^}]*)\}/)?.[1] || ''
    expect(mapRule).not.toContain('height: 100%')
  })

  it('does not send internal Vite file URLs to the browser through development logs', () => {
    const config = readFileSync(fileURLToPath(new URL('../nuxt.config.ts', import.meta.url)), 'utf8')
    expect(config).toContain('devLogs: false')
  })

  it('keeps the overview read-only and places metric editing on its own management page', () => {
    const facts = appFile('components/analysis/FastFacts.vue')
    const editor = appFile('components/analysis/FastFactsEditor.vue')
    const page = appFile('pages/verwaltung/kennzahlen.vue')
    expect(facts).not.toContain('FastFactsEditor')
    expect(facts).not.toContain('Bearbeiten')
    expect(page).toContain("middleware: 'verwaltung'")
    expect(page).toContain('<FastFactsEditor />')
    expect(editor).toContain('type="number"')
    expect(editor).toContain("typeof value === 'number'")
    expect(editor).toContain("analytics.updateFastFacts(payload)")
    expect(editor).not.toContain('contenteditable')
  })
})
