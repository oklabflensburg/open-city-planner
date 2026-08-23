import { describe, expect, it, vi } from 'vitest'
import { requestIdFor, routeTemplate } from '../server/utils/observability'

describe('frontend request correlation', () => {
  it('accepts bounded safe request IDs and replaces unsafe input', () => {
    expect(requestIdFor('edge-123')).toBe('edge-123')
    expect(requestIdFor('bad value')).not.toBe('bad value')
    expect(requestIdFor('x'.repeat(97))).not.toBe('x'.repeat(97))
  })

  it('uses low-cardinality templates for dynamic SSR routes', () => {
    expect(routeTemplate('/flaechen/innenstadt')).toBe('/flaechen/{slug}')
    expect(routeTemplate('/flaechen/hafen')).toBe('/flaechen/{slug}')
    expect(routeTemplate('/gebiete/nordstadt')).toBe('/gebiete/{slug}')
    expect(routeTemplate('/admin/users/123')).toBe('/admin/users/{id}')
  })

  it('generates an ID when none is supplied', () => {
    const randomUUID = vi.spyOn(crypto, 'randomUUID').mockReturnValue('generated-id')
    expect(requestIdFor()).toBe('generated-id')
    randomUUID.mockRestore()
  })
})
