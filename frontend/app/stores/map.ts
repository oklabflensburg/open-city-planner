import { defineStore } from 'pinia'
import type { MapTheme } from '~/utils/mapThemes'
import type { SelectedMapEntity } from '~/types/mapSelection'
import { markRaw } from 'vue'
import type { SelectedMapFeature } from '#frontend-module-sdk'

export type DrawingMode = 'select' | 'polygon' | 'edit' | 'delete'
export type GisPanel = 'filter' | 'selection' | null

export const useMapStore = defineStore('map', {
  state: () => ({
    center: [9.435, 54.783] as [number, number],
    zoom: 16.4,
    bearing: 0,
    pitch: 0,
    activeMode: 'select' as DrawingMode,
    mapLoaded: false,
    activeGisPanel: null as GisPanel,
    selectedMapEntity: null as SelectedMapEntity,
    polygonsVisible: true,
    categoryHighlight: null as string | null,
    thematicStyle: 'category' as MapTheme,
    gisDataGeneration: 0,
    gisDataDirty: false,
    runtimeSelectionClear: null as (() => void) | null,
    runtimeSelectionSelect: null as ((selection: SelectedMapFeature) => Promise<void>) | null,
    runtimeSelection: null as SelectedMapFeature | null
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
    openGisPanel(panel: Exclude<GisPanel, null>) {
      this.activeGisPanel = panel
    },
    closeGisPanel() {
      this.activeGisPanel = null
    },
    closeGisPanels() {
      this.activeGisPanel = null
    },
    connectRuntimeSelection(clear: () => void, select: (selection: SelectedMapFeature) => Promise<void>) {
      const handler = markRaw(clear)
      const selectHandler = markRaw(select)
      this.runtimeSelectionClear = handler
      this.runtimeSelectionSelect = selectHandler
      return () => {
        if (this.runtimeSelectionClear === handler) this.runtimeSelectionClear = null
        if (this.runtimeSelectionSelect === selectHandler) this.runtimeSelectionSelect = null
      }
    },
    setRuntimeSelection(selection: SelectedMapFeature | null) {
      this.runtimeSelection = selection ? markRaw(selection) : null
    },
    async selectRuntimeSelection(selection: SelectedMapFeature) {
      this.setRuntimeSelection(selection)
      await this.runtimeSelectionSelect?.(selection)
    },
    clearRuntimeSelection() {
      this.runtimeSelectionClear?.()
      this.runtimeSelection = null
    },
    markGisDataDirty() {
      this.gisDataGeneration += 1
      this.gisDataDirty = true
    },
    markGisDataFresh() {
      this.gisDataDirty = false
    }
  }
})
