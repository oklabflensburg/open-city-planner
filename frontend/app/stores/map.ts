import { defineStore } from 'pinia'
import type { MapTheme } from '~/utils/mapThemes'
import type { SelectedMapEntity } from '~/types/mapSelection'
import type { FeatureCollection } from 'geojson'
import type { AssistantMapActionType, SearchMapActionType } from '~/types/search'

export type DrawingMode = 'select' | 'polygon' | 'edit' | 'delete'
export type MobilePanel = 'assistant' | 'filter' | 'analytics' | 'selection' | null

export const useMapStore = defineStore('map', {
  state: () => ({
    center: [9.435, 54.783] as [number, number],
    zoom: 16.4,
    bearing: 0,
    pitch: 0,
    activeMode: 'select' as DrawingMode,
    mapLoaded: false,
    activeMobilePanel: null as MobilePanel,
    selectedMapEntity: null as SelectedMapEntity,
    polygonsVisible: true,
    categoryHighlight: null as string | null,
    thematicStyle: 'category' as MapTheme,
    gisDataGeneration: 0,
    gisDataDirty: false,
    searchActionGeneration: 0,
    searchAction: null as {
      type: SearchMapActionType | AssistantMapActionType
      fitBounds: boolean
      bounds: [number, number, number, number] | null
      data: FeatureCollection | null
      areaSlugs: string[]
    } | null
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
      this.activeMobilePanel = panel
    },
    closeMobilePanel() {
      this.activeMobilePanel = null
    },
    closeMobilePanels() {
      this.activeMobilePanel = null
    },
    markGisDataDirty() {
      this.gisDataGeneration += 1
      this.gisDataDirty = true
    },
    markGisDataFresh() {
      this.gisDataDirty = false
    },
    applySearchAction(
      action: { type: SearchMapActionType | AssistantMapActionType, fit_bounds: boolean, bounds: [number, number, number, number] | null, area_slug?: string | null, area_slugs?: string[] },
      data: FeatureCollection | null
    ) {
      const areaSlugs = action.area_slugs?.length ? action.area_slugs : action.area_slug ? [action.area_slug] : []
      this.searchAction = { type: action.type, fitBounds: action.fit_bounds, bounds: action.bounds, data, areaSlugs }
      this.searchActionGeneration += 1
    }
  }
})
