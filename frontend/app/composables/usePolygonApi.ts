import type { AreaGeometry, PolygonEditorDetail, PolygonMetrics, PolygonOverview, PolygonVerwaltungDetail, PublicPolygonDetail, UserPolygon } from '~/types/geo'
import type { PolygonOsmInfo } from '~/types/osm'
import type { ComparableResult, LocationAnalysis } from '~/types/analytics'
import { polygonOverviewSchema, polygonSchema, publicPolygonDetailSchema } from '~/utils/validation'

type PolygonPayload = {
  name: string
  description?: string | null
  category: string
  geometry: AreaGeometry
  properties?: Record<string, unknown>
  floor?: string | null
}

type PublicPolygonPatch = Partial<PolygonPayload> & { area_size?: 'S' | 'M' | 'L' | 'XL' | null; expected_updated_at?: string }
type VerwaltungPatch = Partial<Pick<PolygonVerwaltungDetail,
  'owner_name' | 'owner_street' | 'owner_house_number' | 'owner_postal_code' | 'owner_city' | 'owner_country' | 'price_per_sqm'
  | 'occupancy_status' | 'business_structure'
>> & { expected_updated_at?: string }

export const usePolygonApi = () => {
  const { request } = useApi()

  return {
    async list() {
      const polygons = await request<unknown[]>('/polygons')
      return polygons.map((polygon) => polygonSchema.parse(polygon))
    },
    async overview(query = '', signal?: AbortSignal) {
      const limit = 1000
      const suffix = query ? `?${query}&limit=${limit}` : `?limit=${limit}`
      const polygons = await request<unknown[]>(`/polygons/overview${suffix}`, { signal })
      return polygons.map(polygon => polygonOverviewSchema.parse(polygon)) as PolygonOverview[]
    },
    async create(payload: PolygonPayload) {
      const polygon = polygonSchema.parse(
        await request<UserPolygon>('/polygons', {
          method: 'POST',
          body: JSON.stringify(payload)
        })
      )
      const invalidation = useGisInvalidation()
      invalidation.invalidateAfterPolygonMutation({ type: 'CREATE', polygonId: polygon.id })
      invalidation.showMutationSuccess('CREATE')
      return polygon
    },
    async update(id: string, payload: PublicPolygonPatch) {
      const polygon = polygonSchema.parse(
        await request<UserPolygon>(`/polygons/${id}`, {
          method: 'PATCH',
          body: JSON.stringify(payload)
        })
      )
      useGisInvalidation().invalidateAfterPolygonMutation({ type: 'UPDATE', polygonId: polygon.id })
      return polygon
    },
    async remove(id: string) {
      await request<void>(`/polygons/${id}`, { method: 'DELETE' })
      const invalidation = useGisInvalidation()
      invalidation.invalidateAfterPolygonMutation({ type: 'DELETE', polygonId: id })
      invalidation.showMutationSuccess('DELETE')
    },
    async metrics(id: string) {
      return await request<PolygonMetrics>(`/polygons/${id}/metrics`)
    },
    async bySlug(slug: string) {
      return publicPolygonDetailSchema.parse(
        await request<PublicPolygonDetail>(`/polygons/by-slug/${encodeURIComponent(slug)}`)
      )
    },
    async osmBySlug(slug: string) {
      return await request<PolygonOsmInfo>(`/polygons/by-slug/${encodeURIComponent(slug)}/osm`)
    },
    async locationBySlug(slug: string, radiusM: number) {
      return await request<LocationAnalysis>(`/polygons/by-slug/${encodeURIComponent(slug)}/location?radius_m=${radiusM}`)
    },
    async comparablesBySlug(slug: string) {
      return await request<ComparableResult>(`/polygons/by-slug/${encodeURIComponent(slug)}/comparables`)
    },
    async editor(id: string) {
      return await request<PolygonEditorDetail>(`/polygons/${id}/editor`, { cache: 'no-store' })
    },
    async verwaltung(id: string) {
      return await request<PolygonVerwaltungDetail>(`/polygons/${id}/verwaltung`, { cache: 'no-store' })
    },
    async updateVerwaltung(id: string, payload: VerwaltungPatch) {
      const polygon = await request<PolygonVerwaltungDetail>(`/polygons/${id}/verwaltung`, {
        method: 'PATCH',
        cache: 'no-store',
        body: JSON.stringify(payload)
      })
      useGisInvalidation().invalidateAfterPolygonMutation({ type: 'UPDATE', polygonId: id })
      return polygon
    },
    async geojson() {
      return await request('/polygons/geojson?limit=1000')
    }
  }
}
