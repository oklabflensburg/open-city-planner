import type { ComputedRef } from 'vue'
import type { StyleSpecification } from 'maplibre-gl'

export type ModuleHttpOptions = RequestInit & {
  retryOnUnauthorized?: boolean
}

/** Authenticated, SSR-aware access to the host API. */
export interface ModuleHttpClient {
  request<T>(path: string, options?: ModuleHttpOptions): Promise<T>
}

/** A domain-neutral reference used by the host map selection surface. */
export interface MapSelectionReference {
  readonly type: string
  readonly id: string
}

export interface MapSelectionPort {
  readonly selected: ComputedRef<MapSelectionReference | null>
  clear(): void
}

/** Read-only projection of the currently active host map filters. */
export interface MapFilterPort {
  toQuery(): URLSearchParams
}

/** Loads the host-configured, validated MapLibre style with its normal fallback. */
export interface MapStylePort {
  load(): Promise<StyleSpecification>
}
