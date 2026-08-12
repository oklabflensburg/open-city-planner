import { z } from 'zod'

const positionSchema = z.tuple([z.number().min(-180).max(180), z.number().min(-90).max(90)])

export const polygonGeometrySchema = z.object({
  type: z.literal('Polygon'),
  coordinates: z.array(z.array(positionSchema).min(4)).min(1)
})

export const polygonSchema = z.object({
  id: z.string(),
  slug: z.string(),
  name: z.string(),
  description: z.string().nullable().optional(),
  floor: z.string().nullable().optional(),
  category: z.string(),
  geometry: polygonGeometrySchema,
  properties: z.record(z.unknown()).default({}),
  created_by_user_id: z.string().nullable().optional(),
  updated_by_user_id: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string()
})

export const publicPolygonDetailSchema = z.object({
  id: z.string(),
  slug: z.string(),
  name: z.string(),
  description: z.string().nullable().optional(),
  floor: z.string().nullable().optional(),
  address_display_name: z.string().nullable().optional(),
  address_street: z.string().nullable().optional(),
  address_house_number: z.string().nullable().optional(),
  address_postal_code: z.string().nullable().optional(),
  address_city: z.string().nullable().optional(),
  address_country: z.string().nullable().optional(),
  address_lookup_status: z.enum(['pending', 'resolved', 'failed']),
  category: z.string(),
  geometry: polygonGeometrySchema,
  created_at: z.string(),
  updated_at: z.string(),
  area_m2: z.number(),
  perimeter_m: z.number(),
  centroid: positionSchema,
  bbox: z.tuple([z.number(), z.number(), z.number(), z.number()])
})

export const featureCollectionSchema = z.object({
  type: z.literal('FeatureCollection'),
  features: z.array(
    z.object({
      type: z.literal('Feature'),
      id: z.string().optional(),
      geometry: polygonGeometrySchema,
      properties: z.record(z.unknown()).default({})
    })
  )
})
