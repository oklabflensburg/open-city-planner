export const externalProviders = [
  'google',
  'github',
  'mastodon',
  'openstreetmap',
  'wikipedia'
] as const

export type ExternalProvider = typeof externalProviders[number]
export type OAuthProviderId = Extract<ExternalProvider, 'google' | 'github' | 'mastodon'>

export function isExternalProvider(value: string): value is ExternalProvider {
  return externalProviders.includes(value as ExternalProvider)
}
