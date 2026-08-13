import type { PolygonEditorDetail, PolygonGeometry, PolygonMetrics, PolygonOverview, PolygonVerwaltungDetail, PublicPolygonDetail, UserPolygon } from '~/types/geo'
import type { PolygonOsmInfo } from '~/types/osm'
import { polygonOverviewSchema, polygonSchema, publicPolygonDetailSchema } from '~/utils/validation'

type PolygonPayload = {
  name: string
  description?: string | null
  category: string
  geometry: PolygonGeometry
  properties?: Record<string, unknown>
  floor?: string | null
}

type PublicPolygonPatch = Partial<PolygonPayload> & { area_size?: 'S' | 'M' | 'L' | 'XL' | null; expected_updated_at?: string }
type VerwaltungPatch = Partial<Pick<PolygonVerwaltungDetail,
  'owner_name' | 'owner_street' | 'owner_house_number' | 'owner_postal_code' | 'owner_city' | 'owner_country' | 'price_per_sqm'
>> & { expected_updated_at?: string }

export const usePolygonApi = () => {
  const { request } = useApi()

  return {
    async list() {
      const polygons = await request<unknown[]>('/polygons')
      return polygons.map((polygon) => polygonSchema.parse(polygon))
    },
    async overview() {
      const polygons = await request<unknown[]>('/polygons/overview')
      return polygons.map(polygon => polygonOverviewSchema.parse(polygon)) as PolygonOverview[]
    },
    async create(payload: PolygonPayload) {
      return polygonSchema.parse(
        await request<UserPolygon>('/polygons', {
          method: 'POST',
          body: JSON.stringify(payload)
        })
      )
    },
    async update(id: string, payload: PublicPolygonPatch) {
      return polygonSchema.parse(
        await request<UserPolygon>(`/polygons/${id}`, {
          method: 'PATCH',
          body: JSON.stringify(payload)
        })
      )
    },
    async remove(id: string) {
      await request<void>(`/polygons/${id}`, { method: 'DELETE' })
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
    async editor(id: string) {
      return await request<PolygonEditorDetail>(`/polygons/${id}/editor`, { cache: 'no-store' })
    },
    async verwaltung(id: string) {
      return await request<PolygonVerwaltungDetail>(`/polygons/${id}/verwaltung`, { cache: 'no-store' })
    },
    async updateVerwaltung(id: string, payload: VerwaltungPatch) {
      return await request<PolygonVerwaltungDetail>(`/polygons/${id}/verwaltung`, {
        method: 'PATCH',
        cache: 'no-store',
        body: JSON.stringify(payload)
      })
    },
    async geojson() {
      return await request('/polygons/geojson')
    }
  }
}
