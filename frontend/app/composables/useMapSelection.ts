import type { OsmViewportFeature } from '~/types/osm'
import type { AnalysisArea } from '~/types/analysisArea'

export type SelectedMapEntity
  = | { type: 'polygon', id: string }
    | { type: 'osm', feature: OsmViewportFeature }
    | { type: 'analysis-area', area: AnalysisArea }
    | null

export function useMapSelection() {
  const polygonStore = usePolygonStore()
  const osmStore = useOsmViewportStore()
  const analysisAreasStore = useAnalysisAreasStore()

  const selectedMapEntity = computed<SelectedMapEntity>(() => {
    if (polygonStore.selectedPolygonId) return { type: 'polygon', id: polygonStore.selectedPolygonId }
    if (osmStore.selectedFeature) return { type: 'osm', feature: osmStore.selectedFeature }
    if (analysisAreasStore.selectedArea) return { type: 'analysis-area', area: analysisAreasStore.selectedArea }
    return null
  })

  async function selectPolygon(id: string) {
    osmStore.clearSelection()
    analysisAreasStore.clearSelection()
    await polygonStore.selectPolygon(id)
  }

  async function selectOsm(feature: OsmViewportFeature) {
    polygonStore.clearSelection()
    analysisAreasStore.clearSelection()
    await osmStore.select(feature)
  }

  async function selectAnalysisArea(id: string) {
    polygonStore.clearSelection()
    osmStore.clearSelection()
    await analysisAreasStore.select(id)
  }

  function clearSelection() {
    polygonStore.clearSelection()
    osmStore.clearSelection()
    analysisAreasStore.clearSelection()
  }

  return { selectedMapEntity, selectPolygon, selectOsm, selectAnalysisArea, clearSelection }
}
