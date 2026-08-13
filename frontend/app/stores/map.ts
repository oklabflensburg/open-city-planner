import { defineStore } from 'pinia'

export type DrawingMode = 'select' | 'polygon' | 'edit' | 'delete'
export type MobilePanel = 'filter' | 'analytics' | null

export const useMapStore = defineStore('map', {
  state: () => ({
    center: [9.435, 54.783] as [number, number],
    zoom: 16.4,
    bearing: 0,
    pitch: 0,
    activeMode: 'select' as DrawingMode,
    mapLoaded: false,
    activeMobilePanel: null as MobilePanel,
    polygonPreviewOpen: false,
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
    },
    openMobilePanel(panel: Exclude<MobilePanel, null>) {
      this.polygonPreviewOpen = false
      this.activeMobilePanel = panel
    },
    closeMobilePanel() {
      this.activeMobilePanel = null
    },
    closeMobilePanels() {
      this.activeMobilePanel = null
      this.polygonPreviewOpen = false
    }
  }
})
