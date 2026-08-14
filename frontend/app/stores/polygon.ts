import { defineStore } from 'pinia'
import { markRaw } from 'vue'
import type { PolygonMetrics, PolygonOverview } from '~/types/geo'

export const usePolygonStore = defineStore('polygon', {
  state: () => ({
    polygons: [] as PolygonOverview[],
    selectedPolygonId: null as string | null,
    selectedMetrics: null as PolygonMetrics | null,
    loading: false,
    saving: false,
    error: null as string | null,
    saveState: 'idle' as 'idle' | 'saving' | 'saved' | 'error'
  }),
  getters: {
    selectedPolygon: (state) => state.polygons.find((polygon) => polygon.id === state.selectedPolygonId) || null,
    featureCollection: (state) => ({
      type: 'FeatureCollection' as const,
      features: state.polygons.map((polygon) => ({
        type: 'Feature' as const,
        id: polygon.id,
        geometry: polygon.geometry,
        properties: {
          id: polygon.id,
          name: polygon.name,
          category: polygon.category,
          floor: polygon.floor,
          size: polygon.area_size,
          slug: polygon.slug,
          address: polygon.address_display_name,
          occupancy_status: polygon.occupancy_status,
          business_structure: polygon.business_structure
        }
      }))
    })
  },
  actions: {
    async loadPolygons() {
      this.loading = true
      this.error = null
      try {
        this.polygons = markRaw(await usePolygonApi().overview())
      } catch (error) {
        this.error = error instanceof Error ? error.message : 'Polygone konnten nicht geladen werden.'
      } finally {
        this.loading = false
      }
    },
    async selectPolygon(id: string | null) {
      this.selectedPolygonId = id
      this.selectedMetrics = null
      if (id) {
        try {
          this.selectedMetrics = await usePolygonApi().metrics(id)
        } catch {
          this.selectedMetrics = null
        }
      }
    },
    clearSelection() {
      this.selectedPolygonId = null
      this.selectedMetrics = null
    }
  }
})
