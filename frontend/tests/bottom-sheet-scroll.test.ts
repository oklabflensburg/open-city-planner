import { describe, expect, it, vi } from 'vitest'
import { resetBottomSheetScroll, shouldResetBottomSheetScroll } from '~/utils/bottomSheetScroll'

describe('bottom sheet scroll reset', () => {
  it('resets on first open and every reopen, including the same content', () => {
    expect(shouldResetBottomSheetScroll(true, false, 'analytics', 'analytics')).toBe(true)
    expect(shouldResetBottomSheetScroll(false, true, 'analytics', 'analytics')).toBe(false)
    expect(shouldResetBottomSheetScroll(true, false, 'analytics', 'analytics')).toBe(true)
  })

  it('resets when the identity changes while the sheet remains open', () => {
    expect(shouldResetBottomSheetScroll(true, true, 'polygon:b', 'polygon:a')).toBe(true)
    expect(shouldResetBottomSheetScroll(true, true, 'osm:way:2', 'osm:node:1')).toBe(true)
    expect(shouldResetBottomSheetScroll(true, true, 'analysis-area:b', 'analysis-area:a')).toBe(true)
    expect(shouldResetBottomSheetScroll(true, true, 'analytics', 'filter')).toBe(true)
  })

  it('does not reset reactive updates that keep the same content identity', () => {
    const unchangedCases = ['polygon:a', 'osm:node:1', 'analysis-area:a', 'filter', 'analytics']
    for (const contentKey of unchangedCases) {
      expect(shouldResetBottomSheetScroll(true, true, contentKey, contentKey)).toBe(false)
    }
  })

  it('scrolls the internal container to the top without animation', async () => {
    let scrollTop = 500
    const scrollTo = vi.fn((options: ScrollToOptions) => { scrollTop = options.top as number })

    await resetBottomSheetScroll(() => ({ scrollTo }))

    expect(scrollTop).toBe(0)
    expect(scrollTo).toHaveBeenCalledOnce()
    expect(scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'auto' })
  })
})
