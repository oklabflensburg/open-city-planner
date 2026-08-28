import type { ComputedRef } from 'vue'
import type { StyleSpecification } from 'maplibre-gl'

export type ModuleHttpOptions = RequestInit & {
  retryOnUnauthorized?: boolean
}

export type ModuleStructuredData = Record<string, unknown> | Record<string, unknown>[]

/** Stable, domain-neutral SEO metadata rendered by the host's existing SEO runtime. */
export interface ModuleSeoOptions {
  title: string
  description: string
  path?: string
  siteUrl?: string
  image?: string | null
  imageAlt?: string | null
  imageWidth?: number
  imageHeight?: number
  type?: 'website' | 'article'
  robots?: string
  openGraph?: boolean
  twitter?: boolean
  structuredData?: ModuleStructuredData | false
}

/** Authenticated, SSR-aware access to the host API. */
export interface ModuleHttpClient {
  request<T>(path: string, options?: ModuleHttpOptions): Promise<T>
}

/** Read-only projection of the current host session for module presentation. */
export interface ModuleSessionPort {
  readonly authenticated: ComputedRef<boolean>
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
