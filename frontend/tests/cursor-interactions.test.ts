import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { mapCursorValue, setMapCursor } from '../app/utils/mapCursor'

const appFile = (path: string) => readFileSync(fileURLToPath(new URL(`../app/${path}`, import.meta.url)), 'utf8')

describe('desktop interaction cursors', () => {
  it('defines active and disabled states in the shared controls', () => {
    const button = appFile('components/ui/Button.vue')
    const iconButton = appFile('components/ui/IconButton.vue')
    const css = appFile('assets/css/main.css')

    for (const source of [button, iconButton]) {
      expect(source).toContain('cursor-pointer')
      expect(source).toContain('disabled:cursor-not-allowed')
    }
    expect(css).toContain('cursor: pointer;')
    expect(css).toContain('.page-button-primary:disabled')
    expect(css).toContain('select.field-input')
    expect(css).toContain('input.field-input')
  })

  it('keeps static cards neutral while switches, tabs and notification rows are interactive', () => {
    expect(appFile('components/ui/Card.vue')).not.toContain('cursor-pointer')
    expect(appFile('components/filters/GisFilterToggleRow.vue')).toContain('cursor-pointer')
    expect(appFile('components/notifications/NotificationCenterContent.vue')).toContain('cursor-pointer')
  })

  it('maps every GIS interaction state to a purpose-specific cursor', () => {
    expect(mapCursorValue('pan')).toBe('grab')
    expect(mapCursorValue('dragging')).toBe('grabbing')
    expect(mapCursorValue('interactive')).toBe('pointer')
    expect(mapCursorValue('drawing')).toBe('crosshair')
    expect(mapCursorValue('editing')).toBe('move')

    const canvas = { style: { cursor: '' } } as HTMLCanvasElement
    setMapCursor({ getCanvas: () => canvas }, 'interactive')
    expect(canvas.style.cursor).toBe('pointer')
  })

  it('does not use a global pointer selector', () => {
    const css = appFile('assets/css/main.css')
    expect(css).not.toMatch(/(?:^|\n)\s*\*\s*\{[^}]*cursor\s*:\s*pointer/s)
    expect(css).not.toMatch(/(?:^|\n)\s*button\s*,\s*a[^}]*cursor\s*:\s*pointer/s)
  })
})
