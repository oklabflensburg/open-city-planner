import type { PolygonGeometry } from '~/types/geo'
import type { OsmImportResult } from '~/types/osm'

export function useOsmImport() {
  const importing = ref(false)
  const error = ref('')

  async function importFeature(payload: {
    osm_type: 'node' | 'way' | 'relation'
    osm_id: number
    floor?: string | null
    geometry?: PolygonGeometry
  }) {
    importing.value = true
    error.value = ''
    try {
      const result = await useApi().request<OsmImportResult>('/polygons/from-osm', {
        method: 'POST',
        body: JSON.stringify(payload)
      })
      const invalidation = useGisInvalidation()
      invalidation.invalidateAfterPolygonMutation({
        type: 'ADOPT',
        polygonId: result.id,
        osmType: result.source_osm_type,
        osmId: result.source_osm_id
      })
      invalidation.showMutationSuccess('ADOPT')
      return result
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : 'Die Fläche konnte nicht übernommen werden.'
      throw cause
    } finally {
      importing.value = false
    }
  }

  return { importing, error, importFeature }
}
