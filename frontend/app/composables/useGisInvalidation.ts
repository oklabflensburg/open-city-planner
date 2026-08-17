export function useGisInvalidation() {
  const polygonStore = usePolygonStore()
  const osmStore = useOsmViewportStore()
  const analyticsStore = useAnalyticsStore()
  const mapStore = useMapStore()

  function handlePolygonDeleted(id: string) {
    polygonStore.invalidateDeletedPolygon(id)
    osmStore.invalidateForPolygonMutation()
    analyticsStore.invalidateGisData()
    if (mapStore.selectedMapEntity?.type === 'polygon' && mapStore.selectedMapEntity.id === id) {
      mapStore.selectedMapEntity = null
    }
    mapStore.categoryHighlight = null
    mapStore.markGisDataDirty()
    mapStore.showNotice('Fläche wurde gelöscht.')
  }

  return { handlePolygonDeleted }
}
