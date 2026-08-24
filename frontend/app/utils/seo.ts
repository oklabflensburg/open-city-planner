export function buildAbsoluteUrl(siteUrl: string, path = '/') {
  const base = siteUrl.endsWith('/') ? siteUrl : `${siteUrl}/`
  const relativePath = path.startsWith('/') ? path.slice(1) : path
  return new URL(relativePath, base).toString()
}

export function toMetaDescription(value: string, fallback: string, maxLength = 160) {
  const plainText = value
    .replace(/<[^>]*>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim() || fallback
  if (plainText.length <= maxLength) return plainText
  return `${plainText.slice(0, maxLength - 1).trimEnd()}…`
}

export function serializeStructuredData(value: Record<string, unknown> | Record<string, unknown>[]) {
  return JSON.stringify(value).replace(/</g, '\\u003c')
}

export function buildBreadcrumbStructuredData(
  siteUrl: string,
  items: Array<{ name: string; path: string }>
) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: buildAbsoluteUrl(siteUrl, item.path)
    }))
  }
}

export function buildWebPageStructuredData(
  siteUrl: string,
  path: string,
  name: string,
  description: string
) {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebPage',
    name,
    description,
    url: buildAbsoluteUrl(siteUrl, path),
    isPartOf: {
      '@type': 'WebSite',
      '@id': `${buildAbsoluteUrl(siteUrl, '/')}#website`
    }
  }
}

export function buildCollectionPageStructuredData(
  siteUrl: string,
  path: string,
  name: string,
  description: string
) {
  return {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name,
    description,
    url: buildAbsoluteUrl(siteUrl, path)
  }
}

export function buildItemListStructuredData(
  siteUrl: string,
  name: string,
  items: Array<{ name: string, path: string }>
) {
  return {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name,
    numberOfItems: items.length,
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      url: buildAbsoluteUrl(siteUrl, item.path)
    }))
  }
}

export function buildFaqStructuredData(
  items: Array<{ question: string, answer: string }>
) {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: items.map(item => ({
      '@type': 'Question',
      name: item.question,
      acceptedAnswer: {
        '@type': 'Answer',
        text: item.answer
      }
    }))
  }
}
