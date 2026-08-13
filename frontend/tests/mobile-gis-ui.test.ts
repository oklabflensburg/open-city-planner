import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')

describe('mobile GIS interface', () => {
  it('uses the map as the viewport-height surface below the desktop breakpoint', () => {
    const shell = appFile('components/layout/AppShell.vue')
    expect(shell).toContain('height: calc(100dvh - 4rem)')
    expect(shell).toContain('@media (min-width: 1024px)')
    expect(shell).toContain('lg:grid')
    expect(shell).toContain('lg:hidden')
    expect(shell).toContain('env(safe-area-inset-bottom)')
  })

  it('renders filter and analytics through the exact same bottom-sheet component', () => {
    const shell = appFile('components/layout/AppShell.vue')
    const map = appFile('components/map/MapCanvas.vue')
    const sheetUses = shell.match(/<AppBottomSheet/g) || []
    expect(sheetUses).toHaveLength(2)
    expect(shell).toContain('aria-label="Filter öffnen"')
    expect(shell).toContain('aria-label="Analyse öffnen"')
    expect(shell).toContain('title="Filter & Ansichten"')
    expect(shell).toContain('title="Kennzahlen & Analyse"')
    expect(shell.match(/initial-snap="medium"/g)).toHaveLength(2)
    expect(shell).toContain('label="Ausgewählte Fläche"')
    expect(shell).toContain('filterStore.reset')
    expect(map).toContain('mapStore.polygonPreviewOpen = true')
  })

  it('uses one mutually exclusive mobile panel state', () => {
    const store = appFile('stores/map.ts')
    const shell = appFile('components/layout/AppShell.vue')
    expect(store).toContain("export type MobilePanel = 'filter' | 'analytics' | null")
    expect(store).toContain('activeMobilePanel: null as MobilePanel')
    expect(store).not.toContain('filterDrawerOpen')
    expect(store).not.toContain('analysisDrawerOpen')
    expect(shell).toContain("mapStore.openMobilePanel('filter')")
    expect(shell).toContain("mapStore.openMobilePanel('analytics')")
  })

  it('keeps preview navigation slug-based and OSM data on demand', () => {
    const preview = appFile('components/analysis/PolygonStatistics.vue')
    expect(preview).toContain('/flaechen/${polygon.slug}')
    expect(preview).toContain('osm.loadBySlug')
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
  })

  it('uses identical safe-area, animation and reduced-motion handling', () => {
    const sheet = appFile('components/ui/AppBottomSheet.vue')
    expect(sheet).toContain('env(safe-area-inset-bottom)')
    expect(sheet).toContain("maxHeight: 'calc(100dvh - 0.5rem)'")
    expect(sheet).toContain("window.visualViewport?.addEventListener('resize'")
    expect(sheet).toContain('transition: height 250ms ease-out, transform 250ms ease-out')
    expect(sheet).toContain('@media (prefers-reduced-motion: reduce)')
  })

  it('uses visible loading and retryable error states', () => {
    const map = appFile('components/map/MapCanvas.vue')
    expect(map).toContain('Karte wird geladen')
    expect(map).toContain('Karte konnte nicht geladen werden.')
    expect(map).toContain('Erneut versuchen')
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
