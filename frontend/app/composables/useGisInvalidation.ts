import type { OsmImportResult } from '~/types/osm'

export type GisPolygonMutation =
  | { type: 'CREATE' | 'UPDATE', polygonId: string }
  | { type: 'DELETE', polygonId: string }
  | { type: 'ADOPT', polygonId: string, osmType: OsmImportResult['source_osm_type'], osmId: number }

export function useGisInvalidation() {
  const polygonStore = usePolygonStore()
  const osmStore = useOsmViewportStore()
  const analyticsStore = useAnalyticsStore()
  const mapStore = useMapStore()
  const notifications = useNotificationsStore()

  function invalidateAfterPolygonMutation(mutation: GisPolygonMutation) {
    polygonStore.invalidateForPolygonMutation(mutation.type === 'DELETE' ? mutation.polygonId : undefined)
    osmStore.invalidateForPolygonMutation()
    analyticsStore.invalidateGisData()
    if (mapStore.selectedMapEntity?.type === 'polygon'
      && mapStore.selectedMapEntity.id === mutation.polygonId
      && mutation.type === 'DELETE') {
      mapStore.selectedMapEntity = null
    }
    if (mapStore.selectedMapEntity?.type === 'osm' && mutation.type === 'ADOPT'
      && mapStore.selectedMapEntity.feature.properties.osm_type === mutation.osmType
      && mapStore.selectedMapEntity.feature.properties.osm_id === mutation.osmId) {
      mapStore.selectedMapEntity = null
    }
    mapStore.categoryHighlight = null
    mapStore.markGisDataDirty()
  }

  function showMutationSuccess(type: GisPolygonMutation['type']) {
    const title = type === 'DELETE'
      ? 'Fläche wurde gelöscht.'
      : type === 'ADOPT'
        ? 'Fläche wurde in den Stadtplaner übernommen.'
        : type === 'CREATE'
          ? 'Fläche wurde erstellt.'
          : 'Fläche wurde aktualisiert.'
    notifications.showToast({ title, priority: 'SUCCESS' })
  }

  return { invalidateAfterPolygonMutation, showMutationSuccess }
}
