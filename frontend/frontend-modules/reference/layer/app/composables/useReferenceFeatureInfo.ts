import type {
  MapFeatureInfoProvider,
  MapInteractionEvent,
  SelectedMapFeature
} from '#frontend-module-sdk'

export interface ReferenceFeatureInfo {
  readonly title: string
  readonly description: string
}

interface RenderedReferenceFeature {
  readonly id?: string | number
  readonly properties?: Readonly<Record<string, unknown>>
  readonly geometry?: GeoJSON.Geometry
}

function textProperty(properties: Readonly<Record<string, unknown>> | undefined, key: string) {
  const value = properties?.[key]
  return typeof value === 'string' ? value : ''
}

export function createReferenceFeatureInfoProvider(): MapFeatureInfoProvider<ReferenceFeatureInfo> {
  return {
    id: 'reference.items-info',
    moduleId: 'reference',
    canHandle: selection => selection.moduleId === 'reference' && selection.layerId === 'reference.items',
    resolveFeatureInfo: selection => ({
      title: textProperty(selection.properties, 'title') || 'Referenzmarker',
      description: textProperty(selection.properties, 'description')
    })
  }
}

export function referenceSelectionFrom(event: MapInteractionEvent): SelectedMapFeature | null {
  const feature = event.features?.[0]
  if (!feature || typeof feature !== 'object') return null
  const rendered = feature as RenderedReferenceFeature
  if (rendered.id === undefined) return null
  return {
    moduleId: 'reference',
    sourceId: 'reference.items',
    layerId: 'reference.items',
    featureId: rendered.id,
    properties: rendered.properties,
    geometry: rendered.geometry
  }
}
