import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')

describe('mobile GIS interface', () => {
  it('uses the map as the viewport-height surface below the desktop breakpoint', () => {
    const shell = appFile('components/layout/AppShell.vue')
    expect(shell).toContain('height: calc(100dvh - 4rem)')
    expect(shell).toContain('@media (min-width: 1280px)')
    expect(shell).toContain('xl:grid')
    expect(shell).toContain('xl:hidden')
    expect(shell).toContain('env(safe-area-inset-bottom)')
  })

  it('renders filter, analytics and selection through the exact same bottom-sheet component', () => {
    const shell = appFile('components/layout/AppShell.vue')
    const map = appFile('components/map/MapCanvas.vue')
    const sheetUses = shell.match(/<AppBottomSheet/g) || []
    expect(sheetUses).toHaveLength(1)
    expect(shell).toContain('aria-label="Filter öffnen"')
    expect(shell).toContain('aria-label="Analyse öffnen"')
    expect(shell).toContain(':title="activePanelTitle"')
    expect(shell).toContain("mapStore.activeMobilePanel === 'filter'")
    expect(shell).toContain("mapStore.activeMobilePanel === 'analytics'")
    expect(shell).toContain("mapStore.activeMobilePanel === 'selection'")
    expect(shell.match(/initial-snap="medium"/g)).toHaveLength(1)
    expect(shell).toContain('<MapSelectionContent embedded')
    expect(shell).not.toContain('<Drawer')
    expect(shell).toContain('filterStore.reset')
    expect(map).not.toContain('polygonPreviewOpen')
    expect(map).toContain("mapStore.openMobilePanel('selection')")
  })

  it('keeps embedded filter and analysis summaries in the single sheet scroll flow', () => {
    const shell = appFile('components/layout/AppShell.vue')
    const filter = appFile('components/layout/LeftSidebar.vue')
    const analysis = appFile('components/layout/RightSidebar.vue')
    expect(shell).toContain('<LazyLeftSidebar embedded')
    expect(shell).toContain("mapStore.activeMobilePanel === 'analytics'\" embedded")
    expect(filter).toContain('data-filter-summary')
    expect(filter).toContain("? 'border-b border-slate-200 px-4 pb-3'")
    expect(filter).toContain('<div v-if="!embedded"')
    expect(analysis).toContain('data-analysis-summary')
    expect(analysis).toContain("? 'border-b border-slate-200 px-1 pb-3'")
    expect(analysis).toContain('<div v-if="!embedded"')
  })

  it('uses one mutually exclusive mobile panel state', () => {
    const store = appFile('stores/map.ts')
    const shell = appFile('components/layout/AppShell.vue')
    expect(store).toContain("export type MobilePanel = 'filter' | 'analytics' | 'selection' | null")
    expect(store).toContain('activeMobilePanel: null as MobilePanel')
    expect(store).not.toContain('filterDrawerOpen')
    expect(store).not.toContain('analysisDrawerOpen')
    expect(store).not.toContain('polygonPreviewOpen')
    expect(shell).toContain("mapStore.openMobilePanel('filter')")
    expect(shell).toContain("mapStore.openMobilePanel('analytics')")
  })

  it('keeps preview navigation slug-based and OSM data on demand', () => {
    const preview = appFile('components/analysis/PolygonStatistics.vue')
    const store = appFile('stores/polygon.ts')
    expect(preview).toContain('/flaechen/${polygon.slug}')
    expect(preview).toContain(':info="store.selectedOsmInfo"')
    expect(store).toContain('api.osmBySlug(polygon.slug)')
  })

  it('provides accessible modal, focus and browser-back behavior', () => {
    const sheet = appFile('components/ui/AppBottomSheet.vue')
    const shell = appFile('components/layout/AppShell.vue')
    expect(sheet).toContain('role="dialog"')
    expect(sheet).toContain('aria-modal="true"')
    expect(sheet).toContain(':aria-labelledby="titleId"')
    expect(sheet).toContain("event.key === 'Escape'")
    expect(sheet).toContain("event.key !== 'Tab'")
    expect(sheet).toContain('returnFocusTo?.focus()')
    expect(shell).toContain("window.addEventListener('popstate'")
    expect(shell).not.toContain('requestResize')
  })

  it('shares medium and expanded snap points, gestures and one scroll container', () => {
    const sheet = appFile('components/ui/AppBottomSheet.vue')
    expect(sheet).toContain("value === 'expanded'")
    expect(sheet).toContain('height * 0.94')
    expect(sheet).toContain('height * 0.6')
    expect(sheet).toContain('data-sheet-drag-handle')
    expect(sheet).toContain('data-sheet-scroll')
    expect(sheet).toContain('scroller.value?.scrollTop !== 0')
    expect(sheet).toContain('overscroll-contain')
    expect(sheet).toContain('isInteractiveTarget')
    expect(sheet).toContain('@touchmove="continueContentTouch"')
    expect(sheet).toContain('event.preventDefault()')
    expect(sheet).not.toContain('storedScrollPositions')
    expect(sheet).toContain('props.contentKey')
  })

  it('resets only newly opened or identity-changed sheet content to the top', () => {
    const sheet = appFile('components/ui/AppBottomSheet.vue')
    const shell = appFile('components/layout/AppShell.vue')
    expect(sheet).toContain("watch([() => props.open, () => props.contentKey]")
    expect(sheet).toContain('shouldResetBottomSheetScroll(open, wasOpen, contentKey, previousContentKey)')
    expect(sheet).toContain('resetBottomSheetScroll(() => scroller.value)')
    expect(sheet).not.toContain("behavior: 'smooth'")
    expect(sheet).not.toContain('window.scrollTo')
    expect(shell).toContain("return `polygon:${entity.id}`")
    expect(shell).toContain('return `osm:${entity.feature.properties.osm_type}:${entity.feature.properties.osm_id}`')
    expect(shell).toContain('return `analysis-area:${entity.id}`')
  })

  it('uses identical safe-area, animation and reduced-motion handling', () => {
    const sheet = appFile('components/ui/AppBottomSheet.vue')
    expect(sheet).toContain('env(safe-area-inset-bottom)')
    expect(sheet).toContain("maxHeight: 'calc(100dvh - 0.5rem)'")
    expect(sheet).toContain("window.visualViewport?.addEventListener('resize'")
    expect(sheet).toContain("(scroller.value?.scrollTop || 0) === 0")
    expect(sheet).toContain('transition: height 250ms ease-out, transform 250ms ease-out')
    expect(sheet).toContain('@media (prefers-reduced-motion: reduce)')
  })

  it('uses visible loading and retryable error states', () => {
    const map = appFile('components/map/MapCanvas.vue')
    expect(map).toContain('Karte wird geladen')
    expect(map).toContain('Karte konnte nicht geladen werden.')
    expect(map).toContain('Erneut versuchen')
  })

  it('keeps public GIS controls read-only, understandable and at least 44 pixels large', () => {
    const shell = appFile('components/layout/AppShell.vue')
    const controls = appFile('components/map/MapControls.vue')
    const preview = appFile('components/analysis/PolygonStatistics.vue')
    const hint = appFile('components/layout/LeftSidebar.vue')
    expect(shell).toContain('aria-label="Filter öffnen"')
    expect(shell).toContain('aria-label="Analyse öffnen"')
    expect(shell).toContain('aria-pressed="mapStore.activeMobilePanel')
    expect(shell).toContain('height: 2.75rem')
    expect(shell).toContain('border: 1px solid transparent')
    expect(controls.match(/h-11 w-11/g)).toHaveLength(3)
    expect(preview).toContain('Details anzeigen')
    expect(hint).not.toContain('Bearbeitung')
  })

  it('anchors every upper-right map control in one stable container', () => {
    const map = appFile('components/map/MapCanvas.vue')
    const container = appFile('components/map/MapControlsContainer.vue')
    expect(map).toContain('absolute right-3 top-3')
    expect(map).toContain('<MapControlsContainer')
    expect(map).not.toContain('<MapLayerControl')
    expect(container).toContain('w-11 flex-col')
    expect(container).toContain('<MapControls')
    expect(container).toContain('<MapLayerControl')
  })

  it('keeps the layer button bounding box independent from its open state', () => {
    const layer = appFile('components/map/MapLayerControl.vue')
    expect(layer).toContain('class="relative h-11 w-11"')
    expect(layer).toContain('grid h-11 w-11')
    expect(layer).toContain("'border-slate-200 bg-white text-slate-600'")
    expect(layer).toContain(':aria-expanded="open"')
    expect(layer).toContain('class="absolute bottom-0 right-[calc(100%+0.5rem)] w-52')
    expect(layer).not.toContain('scale-')
    expect(layer).not.toContain('translate-')
    expect(layer).not.toContain('border-2')
  })

  it('keeps mobile create and detail maps large and touch-editable', () => {
    const createMap = appFile('components/polygon/PolygonCreateMap.vue')
    const detailMap = appFile('components/polygon/PolygonDetailMap.vue')
    expect(createMap).toContain('h-[clamp(320px,50dvh,520px)]')
    expect(detailMap).toContain('h-[clamp(320px,46dvh,480px)]')
    expect(detailMap).toContain('touchZoomRotate.disable()')
    expect(detailMap).toContain('touchZoomRotate.enable()')
  })

  it('does not hide horizontal overflow globally as a layout workaround', () => {
    const css = appFile('assets/css/main.css')
    expect(css).not.toMatch(/body\s*\{[^}]*overflow-x:\s*hidden/s)
  })

  it('keeps fixed mobile navigation anchored while it animates', () => {
    const css = appFile('assets/css/main.css')
    const navigationTransition = css.match(/\.mobile-navigation-enter-from,\s*\.mobile-navigation-leave-to\s*\{([^}]*)\}/s)?.[1] || ''
    expect(navigationTransition).toContain('opacity: 0')
    expect(navigationTransition).not.toContain('transform')
    expect(css).toContain('body.mobile-nav-open')
  })
})
