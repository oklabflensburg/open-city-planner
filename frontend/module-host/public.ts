export {
  FRONTEND_HOST_VERSION,
  FRONTEND_MODULE_SDK_VERSION,
  type FrontendModuleCompatibility,
  type FrontendModuleDefinition
} from './contract.ts'
export {
  DEFAULT_UI_CONTRIBUTION_PRIORITY,
  UI_SLOT_IDS,
  type BoundComponentContribution,
  type BoundNavigationContribution,
  type ComponentUiSlotId,
  type FrontendModuleUiContribution,
  type HeaderActionContribution,
  type JsonSafeValue,
  type MapUiControlContribution,
  type NavigationContribution,
  type UiContribution,
  type UiSlotId,
  type UiVisibilityContext,
  type UiVisibilityRule
} from './ui-contract.ts'
export { isUiContributionVisible } from './ui-registry.ts'
export {
  MAP_INTERACTION_EVENTS,
  MAP_LAYER_GROUPS,
  type DrawAdapter,
  type DrawManagerApi,
  type BoundMapLayerContribution,
  type BoundMapSourceContribution,
  type FrontendModuleMapContributions,
  type MapAnalysisProvider,
  type MapAnalysisRegistryApi,
  type MapContext,
  type MapControlContribution,
  type MapControlRegistryApi,
  type MapFacade,
  type MapFeatureInfoProvider,
  type MapFeatureInfoRegistryApi,
  type MapFeatureQueryApi,
  type MapFeatureQueryOptions,
  type MapInteractionContribution,
  type MapInteractionRegistryApi,
  type MapInteractionEvent,
  type MapInteractionEventName,
  type MapInteractionResult,
  type MapLayerDefinition,
  type MapLayerContribution,
  type MapLayerGroup,
  type MapSelectionPresentation,
  type MapSourceContribution,
  type MapTelemetry,
  type SelectedMapFeature,
  type SelectionManagerApi
} from './map-contract.ts'
export { MAP_CONTEXT_KEY, useMapContext } from './map-vue.ts'
export {
  type MapFilterPort,
  type MapSelectionPort,
  type MapSelectionReference,
  type MapStylePort,
  type ModuleHttpClient,
  type ModuleHttpOptions
} from './platform-contract.ts'
export {
  useMapFilterPort,
  useMapSelectionPort,
  useMapStylePort,
  useModuleHttp
} from './platform-vue.ts'
export {
  externalProviders,
  isExternalProvider,
  type ExternalProvider
} from '../app/types/externalProvider.ts'
export {
  mapCursorValue,
  setMapCursor,
  type MapCursorState
} from '../app/utils/mapCursor.ts'
export {
  buildAbsoluteUrl,
  buildBreadcrumbStructuredData,
  buildCollectionPageStructuredData,
  buildFaqStructuredData,
  buildItemListStructuredData,
  buildSeoImageUrl,
  serializeStructuredData,
  toMetaDescription
} from '../app/utils/seo'
export { getIndustryColor, getIndustryLabel } from '../app/utils/industries'
export { areaPoiMapLink, getPoiCategoryLabel } from '../app/utils/poiCategories'
