import { z } from 'zod'

const positionSchema = z.tuple([z.number().min(-180).max(180), z.number().min(-90).max(90)])

export const polygonGeometrySchema = z.object({
  type: z.literal('Polygon'),
  coordinates: z.array(z.array(positionSchema).min(4)).min(1)
})

export const multiPolygonGeometrySchema = z.object({
  type: z.literal('MultiPolygon'),
  coordinates: z.array(z.array(z.array(positionSchema).min(4)).min(1)).min(1)
})

export const areaGeometrySchema = z.union([polygonGeometrySchema, multiPolygonGeometrySchema])

export const polygonSchema = z.object({
  id: z.string(),
  slug: z.string(),
  name: z.string(),
  description: z.string().nullable().optional(),
  floor: z.string().nullable().optional(),
  category: z.string(),
  geometry: areaGeometrySchema,
  properties: z.record(z.string(), z.unknown()).default({}),
  created_by_user_id: z.string().nullable().optional(),
  updated_by_user_id: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string()
})

export const publicPolygonSchema = z.object({
  id: z.string(),
  slug: z.string(),
  name: z.string(),
  description: z.string().nullable().optional(),
  floor: z.string().nullable().optional(),
  category: z.string(),
  geometry: areaGeometrySchema,
  properties: z.record(z.string(), z.unknown()).default({}),
  created_at: z.string(),
  updated_at: z.string()
})

export const polygonOverviewSchema = z.object({
  id: z.string(),
  slug: z.string(),
  name: z.string(),
  category: z.string(),
  floor: z.string().nullable().optional(),
  area_size: z.string().nullable().optional(),
  address_display_name: z.string().nullable().optional(),
  occupancy_status: z.enum(['OCCUPIED', 'VACANT', 'UNKNOWN']),
  business_structure: z.enum(['CHAIN', 'INDEPENDENT', 'UNKNOWN']),
  geometry: areaGeometrySchema,
  created_at: z.string(),
  updated_at: z.string()
})

const externalLinksSchema = z.object({
  wikipedia: z.object({ title: z.string(), url: z.string().url() }).nullable()
}).default({ wikipedia: null })

export const publicPolygonDetailSchema = z.object({
  id: z.string(),
  slug: z.string(),
  name: z.string(),
  description: z.string().nullable().optional(),
  floor: z.string().nullable().optional(),
  area_size: z.enum(['S', 'M', 'L', 'XL']).nullable().optional(),
  address_display_name: z.string().nullable().optional(),
  address_street: z.string().nullable().optional(),
  address_house_number: z.string().nullable().optional(),
  address_postal_code: z.string().nullable().optional(),
  address_city: z.string().nullable().optional(),
  address_country: z.string().nullable().optional(),
  address_lookup_status: z.enum(['pending', 'resolved', 'failed']),
  category: z.string(),
  occupancy_status: z.enum(['OCCUPIED', 'VACANT', 'UNKNOWN']),
  occupancy_source: z.enum(['OSM', 'MANUAL', 'IMPORTED', 'CALCULATED', 'UNKNOWN']).default('UNKNOWN'),
  business_structure: z.enum(['CHAIN', 'INDEPENDENT', 'UNKNOWN']),
  geometry: areaGeometrySchema,
  osm_sources: z.array(z.object({
    osm_type: z.enum(['node', 'way', 'relation']),
    osm_id: z.number(),
    is_primary: z.boolean(),
    imported_at: z.string(),
    external_links: externalLinksSchema
  })).default([]),
  external_links: externalLinksSchema,
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
      geometry: areaGeometrySchema,
      properties: z.record(z.string(), z.unknown()).default({})
    })
  )
})
