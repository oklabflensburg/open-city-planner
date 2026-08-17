export function useGisInvalidation() {
  const polygonStore = usePolygonStore()
  const osmStore = useOsmViewportStore()
  const analyticsStore = useAnalyticsStore()
  const mapStore = useMapStore()
  const notifications = useNotificationsStore()

  function handlePolygonDeleted(id: string) {
    polygonStore.invalidateDeletedPolygon(id)
    osmStore.invalidateForPolygonMutation()
    analyticsStore.invalidateGisData()
    if (mapStore.selectedMapEntity?.type === 'polygon' && mapStore.selectedMapEntity.id === id) {
      mapStore.selectedMapEntity = null
    }
    mapStore.categoryHighlight = null
    mapStore.markGisDataDirty()
    notifications.showToast({ title: 'Fläche wurde gelöscht.', priority: 'SUCCESS' })
  }

  return { handlePolygonDeleted }
}
