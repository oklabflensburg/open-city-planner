import { defineStore } from 'pinia'
import type { PolygonGeometry, PolygonMetrics, UserPolygon } from '~/types/geo'

export const usePolygonStore = defineStore('polygon', {
  state: () => ({
    polygons: [] as UserPolygon[],
    selectedPolygonId: null as string | null,
    drawingPolygon: null as PolygonGeometry | null,
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
          ...polygon.properties,
          id: polygon.id,
          name: polygon.name,
          category: polygon.category
        }
      }))
    })
  },
  actions: {
    async loadPolygons() {
      this.loading = true
      this.error = null
      try {
        this.polygons = await usePolygonApi().list()
      } catch (error) {
        this.error = error instanceof Error ? error.message : 'Polygone konnten nicht geladen werden.'
      } finally {
        this.loading = false
      }
    },
    async createPolygon(payload: { name: string; description?: string | null; category: string; geometry: PolygonGeometry; properties?: Record<string, unknown> }) {
      this.saving = true
      this.saveState = 'saving'
      try {
        const polygon = await usePolygonApi().create(payload)
        this.polygons.push(polygon)
        this.selectedPolygonId = polygon.id
        this.saveState = 'saved'
        return polygon
      } catch (error) {
        this.saveState = 'error'
        this.error = error instanceof Error ? error.message : 'Polygon konnte nicht gespeichert werden.'
        throw error
      } finally {
        this.saving = false
      }
    },
    async updatePolygon(id: string, payload: Partial<{ name: string; description: string | null; category: string; geometry: PolygonGeometry; properties: Record<string, unknown> }>) {
      this.saving = true
      this.saveState = 'saving'
      try {
        const polygon = await usePolygonApi().update(id, payload)
        const current = this.polygons.find((item) => item.id === id)
        const merged = {
          ...polygon,
          category: payload.category ?? current?.category ?? polygon.category,
          properties: payload.properties ?? current?.properties ?? polygon.properties
        }
        this.polygons = this.polygons.map((item) => (item.id === id ? merged : item))
        this.saveState = 'saved'
        return merged
      } catch (error) {
        this.saveState = 'error'
        this.error = error instanceof Error ? error.message : 'Polygon konnte nicht aktualisiert werden.'
        throw error
      } finally {
        this.saving = false
      }
    },
    async deletePolygon(id: string) {
      await usePolygonApi().remove(id)
      this.polygons = this.polygons.filter((polygon) => polygon.id !== id)
      if (this.selectedPolygonId === id) {
        this.clearSelection()
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
