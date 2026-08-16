export type NavigationItem = {
  label: string
  to: string
}

export function useSiteNavigation() {
  const primaryNavigation: NavigationItem[] = [
    { label: 'Karte', to: '/' },
    { label: 'Gebiete', to: '/gebiete' },
    { label: 'Über das Projekt', to: '/ueber-das-projekt' },
    { label: 'Dokumentation', to: '/dokumentation' }
  ]

  const legalNavigation: NavigationItem[] = [
    { label: 'Impressum', to: '/impressum' },
    { label: 'Datenschutz', to: '/datenschutz' }
  ]

  return {
    primaryNavigation,
    legalNavigation
  }
}
