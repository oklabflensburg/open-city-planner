import { setActivePinia, createPinia } from 'pinia'
import { describe, expect, it, beforeEach } from 'vitest'
import { useFilterStore } from '~/stores/filter'
import { industries } from '~/utils/industries'

describe('filter store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('toggles all industry categories', () => {
    const store = useFilterStore()
    expect(store.activeCategories).toHaveLength(industries.length)
    store.toggleAll()
    expect(store.activeCategories).toEqual([])
    store.toggleAll()
    expect(store.activeCategories).toHaveLength(industries.length)
  })

  it('toggles a single category', () => {
    const store = useFilterStore()
    store.toggleCategory('fashion')
    expect(store.activeCategories).not.toContain('fashion')
    store.toggleCategory('fashion')
    expect(store.activeCategories).toContain('fashion')
  })
})

