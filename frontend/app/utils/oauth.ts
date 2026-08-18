import type { OAuthProvider } from '~/types/auth'

export type OAuthMode = 'login' | 'signup'

export function hasOAuthProviders(providers: OAuthProvider[]): boolean {
  return providers.length > 0
}

export function oauthButtonLabel(providerLabel: string, mode: OAuthMode): string {
  void mode
  return `Mit ${providerLabel} fortfahren`
}
