import { useAsyncData, useRuntimeConfig } from '#imports'
import { referenceApiUrl } from './referenceApi'

export interface ReferenceItemRead {
  readonly id: string
  readonly title: string
  readonly description: string
  readonly longitude: number
  readonly latitude: number
}

export function useReferenceItems() {
  const config = useRuntimeConfig()
  const baseUrl = import.meta.server
    ? String(config.apiInternalBaseUrl || config.public.apiBaseUrl)
    : String(config.public.apiBaseUrl)
  return useAsyncData(
    'reference-items',
    () => $fetch<ReferenceItemRead[]>(referenceApiUrl(baseUrl))
  )
}
