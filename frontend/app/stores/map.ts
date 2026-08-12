import { defineStore } from 'pinia'

export type DrawingMode = 'select' | 'polygon' | 'edit' | 'delete'

export const useMapStore = defineStore('map', {
  state: () => ({
    center: [9.435, 54.783] as [number, number],
    zoom: 16.4,
    bearing: 0,
    pitch: 0,
    activeMode: 'select' as DrawingMode,
    mapLoaded: false,
    filterDrawerOpen: false,
    analysisDrawerOpen: false,
    categoryHighlight: null as string | null
  }),
  actions: {
    setView(center: [number, number], zoom: number, bearing: number, pitch: number) {
      this.center = center
      this.zoom = zoom
      this.bearing = bearing
      this.pitch = pitch
    },
    setMode(mode: DrawingMode) {
      this.activeMode = mode
    },
    resetView(center: [number, number], zoom: number) {
      this.center = center
      this.zoom = zoom
      this.bearing = 0
      this.pitch = 0
    }
  }
})

