import type { OsmViewportFeature } from '~/types/osm'

export type SelectedMapEntity
  = | { type: 'polygon', id: string }
    | { type: 'osm', feature: OsmViewportFeature }
    | { type: 'analysis-area', id: string }
    | null
