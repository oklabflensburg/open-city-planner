import type { OsmViewportFeature } from '~/types/osm'

export function useMapSelection() {
  const mapStore = useMapStore()
  const polygonStore = usePolygonStore()
  const osmStore = useOsmViewportStore()
  const analysisAreasStore = useAnalysisAreasStore()

  const selectedMapEntity = computed(() => mapStore.selectedMapEntity)

  async function selectPolygon(id: string) {
    mapStore.clearRuntimeSelection()
    clearSelectionData()
    mapStore.selectedMapEntity = { type: 'polygon', id }
    await polygonStore.loadSelection(id)
  }

  async function selectOsm(feature: OsmViewportFeature) {
    mapStore.clearRuntimeSelection()
    clearSelectionData()
    mapStore.selectedMapEntity = { type: 'osm', feature }
    await osmStore.loadDetail(feature)
  }

  async function selectAnalysisArea(id: string) {
    mapStore.clearRuntimeSelection()
    clearSelectionData()
    mapStore.selectedMapEntity = { type: 'analysis-area', id }
    await analysisAreasStore.loadDetails(id)
  }

  function clearSelection() {
    mapStore.clearRuntimeSelection()
    mapStore.selectedMapEntity = null
    clearSelectionData()
  }

  function clearSelectionData() {
    polygonStore.clearSelection()
    osmStore.clearSelection()
    analysisAreasStore.clearSelection()
  }

  return { selectedMapEntity, selectPolygon, selectOsm, selectAnalysisArea, clearSelection }
}
