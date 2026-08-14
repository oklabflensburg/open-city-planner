import { defineStore } from 'pinia'
import type { MapTheme } from '~/utils/mapThemes'

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
    polygonsVisible: true,
    categoryHighlight: null as string | null,
    thematicStyle: 'category' as MapTheme
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
    setPolygonsVisible(visible: boolean) {
      this.polygonsVisible = visible
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
