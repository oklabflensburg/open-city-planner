import type { FrontendModuleUiContribution, MapLayerContribution, MapSourceContribution } from '#frontend-module-sdk'

export const validNavigationContribution: FrontendModuleUiContribution = {
  id: 'type-test.primary-navigation',
  slot: 'navigation.primary',
  label: 'Typprüfung',
  to: '/'
}

export const invalidNavigationContribution: FrontendModuleUiContribution = {
  id: 'type-test.invalid-navigation',
  slot: 'navigation.primary',
  // @ts-expect-error Navigation slots reject component payloads at type-check time.
  component: 'UnsafeHtmlReplacement',
  source: 'component.vue'
}

export const invalidSlotContribution: FrontendModuleUiContribution = {
  id: 'type-test.invalid-slot',
  // @ts-expect-error Unknown slot IDs fail the public SDK type-check.
  slot: 'unknown.slot',
  label: 'Ungültig',
  to: '/'
}

export const validMapSource: MapSourceContribution = {
  id: 'type-test.landmark',
  source: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
}

export const validMapLayer: MapLayerContribution = {
  id: 'type-test.landmark',
  sourceId: validMapSource.id,
  group: 'overlay',
  layer: { type: 'circle', paint: { 'circle-color': '#154d73' } }
}
