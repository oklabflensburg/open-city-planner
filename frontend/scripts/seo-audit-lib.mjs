const LOCAL_HOST_PATTERN = /(?:localhost|127\.0\.0\.1|\[?::1\]?)/i
const KNOWN_SCHEMA_TYPES = new Set([
  'AdministrativeArea', 'BreadcrumbList', 'CollectionPage', 'FAQPage', 'ItemList',
  'ListItem', 'Place', 'Question', 'Answer', 'SoftwareApplication', 'WebPage', 'WebSite'
])

export function attributes(tag) {
  return Object.fromEntries(
    [...tag.matchAll(/([:\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')/g)]
      .map(match => [match[1].toLowerCase(), decodeHtml(match[2] ?? match[3] ?? '')])
  )
}

export function decodeHtml(value) {
  return value
    .replaceAll('&quot;', '"')
    .replaceAll('&#39;', "'")
    .replaceAll('&apos;', "'")
    .replaceAll('&lt;', '<')
    .replaceAll('&gt;', '>')
    .replaceAll('&amp;', '&')
    .replace(/&#(\d+);/g, (_match, code) => String.fromCodePoint(Number(code)))
    .replace(/&#x([\da-f]+);/gi, (_match, code) => String.fromCodePoint(Number.parseInt(code, 16)))
}

export function parseHtmlSeo(html) {
  const meta = [...html.matchAll(/<meta\b[^>]*>/gi)].map(match => attributes(match[0]))
  const links = [...html.matchAll(/<link\b[^>]*>/gi)].map(match => attributes(match[0]))
  const titles = [...html.matchAll(/<title\b[^>]*>([\s\S]*?)<\/title>/gi)]
    .map(match => textContent(match[1]))
  const headings = [...html.matchAll(/<h1\b[^>]*>([\s\S]*?)<\/h1>/gi)]
    .map(match => textContent(match[1]))
  const jsonLd = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\b[^>]*>/gi)]
    .filter(match => attributes(`<script ${match[1]}>`).type === 'application/ld+json')
    .map(match => decodeHtml(match[2]).trim())
  return { meta, links, titles, headings, jsonLd }
}

export function auditIndexableHtml(html, { expectedUrl, expectSocialImage = true } = {}) {
  const errors = []
  const page = parseHtmlSeo(html)
  const canonical = page.links.filter(item => item.rel === 'canonical')
  const description = namedMeta(page.meta, 'description')
  const robots = namedMeta(page.meta, 'robots')
  const canonicalUrl = canonical[0]?.href

  if (page.titles.length !== 1) errors.push(`expected exactly one title, received ${page.titles.length}`)
  else if (page.titles[0].length < 3) errors.push('title is empty or too short')
  if (description.length !== 1 || !description[0].content?.trim()) errors.push('missing or empty meta description')
  if (robots.length !== 1 || robots[0].content !== 'index,follow') errors.push('expected robots=index,follow')
  if (canonical.length !== 1) errors.push(`expected exactly one canonical, received ${canonical.length}`)
  if (!page.headings.some(Boolean)) errors.push('missing non-empty SSR h1')

  if (canonicalUrl) {
    validatePublicUrl(canonicalUrl, 'canonical', errors)
    if (expectedUrl && canonicalUrl !== expectedUrl) errors.push(`canonical is ${canonicalUrl}, expected ${expectedUrl}`)
    try {
      if (new URL(canonicalUrl).search) errors.push('canonical contains query parameters')
    } catch { /* reported by validatePublicUrl */ }
  }

  for (const key of ['og:title', 'og:description', 'og:url', 'og:type', 'og:site_name', 'og:locale']) {
    const values = propertyMeta(page.meta, key)
    if (values.length !== 1 || !values[0].content?.trim()) errors.push(`missing or duplicate ${key}`)
  }
  if (canonicalUrl && propertyMeta(page.meta, 'og:url')[0]?.content !== canonicalUrl) {
    errors.push('og:url does not match canonical')
  }
  for (const key of ['twitter:card', 'twitter:title', 'twitter:description']) {
    const values = namedMeta(page.meta, key)
    if (values.length !== 1 || !values[0].content?.trim()) errors.push(`missing or duplicate ${key}`)
  }
  const twitterSite = namedMeta(page.meta, 'twitter:site')
  if (twitterSite.length !== 1 || twitterSite[0].content !== '@oklabflensburg') {
    errors.push('expected twitter:site=@oklabflensburg')
  }
  if (expectSocialImage) {
    for (const [kind, key] of [['property', 'og:image'], ['property', 'og:image:alt'], ['name', 'twitter:image'], ['name', 'twitter:image:alt']]) {
      const values = kind === 'property' ? propertyMeta(page.meta, key) : namedMeta(page.meta, key)
      if (values.length !== 1 || !values[0].content?.trim()) errors.push(`missing or duplicate ${key}`)
    }
    if (namedMeta(page.meta, 'twitter:card')[0]?.content !== 'summary_large_image') {
      errors.push('expected twitter:card=summary_large_image')
    }
    if (propertyMeta(page.meta, 'og:image:width')[0]?.content !== '1200') {
      errors.push('expected og:image:width=1200')
    }
    if (propertyMeta(page.meta, 'og:image:height')[0]?.content !== '630') {
      errors.push('expected og:image:height=630')
    }
  }

  auditGlobalHead(page, errors)

  auditSeoUrls(page, errors)
  auditJsonLd(page.jsonLd, errors)
  return errors
}

function auditGlobalHead(page, errors) {
  const theme = namedMeta(page.meta, 'theme-color')
  if (theme.length !== 1 || theme[0].content !== '#154d73') errors.push('expected theme-color=#154d73')
  for (const [rel, href] of [
    ['icon', '/favicon.ico'],
    ['icon', '/branding/ok-lab-flensburg.svg'],
    ['icon', '/favicon-96x96.png'],
    ['apple-touch-icon', '/apple-touch-icon.png'],
    ['manifest', '/site.webmanifest']
  ]) {
    if (!page.links.some(item => item.rel === rel && item.href === href)) errors.push(`missing global ${rel} ${href}`)
  }
}

export function auditNoindexHtml(html, { canonicalUrl, expectedRobots = 'noindex,nofollow' } = {}) {
  const errors = []
  const page = parseHtmlSeo(html)
  const robots = namedMeta(page.meta, 'robots')
  if (robots.length !== 1 || robots[0].content !== expectedRobots) {
    errors.push(`expected robots=${expectedRobots}`)
  }
  if (canonicalUrl) {
    const canonicals = page.links.filter(item => item.rel === 'canonical')
    if (canonicals.length !== 1 || canonicals[0].href !== canonicalUrl) {
      errors.push(`expected canonical ${canonicalUrl}`)
    }
  }
  auditSeoUrls(page, errors)
  auditJsonLd(page.jsonLd, errors)
  return errors
}

export function auditNotFoundHtml(html) {
  const errors = auditNoindexHtml(html)
  const page = parseHtmlSeo(html)
  if (page.links.some(item => item.rel === 'canonical')) errors.push('404 page must not define a canonical')
  if (!page.headings.some(Boolean)) errors.push('404 page has no non-empty SSR h1')
  return errors
}

export function sitemapLocations(xml) {
  return [...xml.matchAll(/<loc>([\s\S]*?)<\/loc>/gi)].map(match => decodeHtml(match[1].trim()))
}

export function robotsDisallowPaths(text) {
  return [...text.matchAll(/^Disallow:\s*(\S+)\s*$/gmi)].map(match => match[1])
}

export function hasLocalHost(value) {
  return LOCAL_HOST_PATTERN.test(value)
}

function namedMeta(meta, name) {
  return meta.filter(item => item.name?.toLowerCase() === name)
}

function propertyMeta(meta, property) {
  return meta.filter(item => item.property?.toLowerCase() === property)
}

function textContent(value) {
  return decodeHtml(value.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim())
}

function validatePublicUrl(value, label, errors) {
  try {
    const url = new URL(value)
    if (url.protocol !== 'https:') errors.push(`${label} must use https`)
    if (hasLocalHost(url.hostname)) errors.push(`${label} points to a local host`)
  } catch {
    errors.push(`${label} is not an absolute URL`)
  }
}

function auditSeoUrls(page, errors) {
  const urls = [
    ...page.links.filter(item => item.rel === 'canonical').map(item => ['canonical', item.href]),
    ...propertyMeta(page.meta, 'og:url').map(item => ['og:url', item.content]),
    ...propertyMeta(page.meta, 'og:image').map(item => ['og:image', item.content]),
    ...namedMeta(page.meta, 'twitter:image').map(item => ['twitter:image', item.content])
  ]
  for (const [label, value] of urls) if (value) validatePublicUrl(value, label, errors)
}

function auditJsonLd(blocks, errors) {
  blocks.forEach((block, index) => {
    let value
    try { value = JSON.parse(block) } catch { errors.push(`invalid JSON-LD block ${index + 1}`); return }
    const entries = Array.isArray(value) ? value : [value]
    for (const entry of entries) validateSchemaEntry(entry, index, errors)
    if (hasLocalHost(JSON.stringify(value))) errors.push(`JSON-LD block ${index + 1} contains a local host`)
  })
}

function validateSchemaEntry(entry, index, errors) {
  if (!entry || typeof entry !== 'object' || Array.isArray(entry)) {
    errors.push(`JSON-LD block ${index + 1} must contain objects`)
    return
  }
  if (entry['@context'] !== 'https://schema.org') errors.push(`JSON-LD block ${index + 1} has an invalid @context`)
  const types = Array.isArray(entry['@type']) ? entry['@type'] : [entry['@type']]
  if (!types.every(type => typeof type === 'string' && type)) errors.push(`JSON-LD block ${index + 1} is missing @type`)
  for (const type of types.filter(type => KNOWN_SCHEMA_TYPES.has(type))) {
    if (['AdministrativeArea', 'CollectionPage', 'Place', 'WebPage', 'WebSite'].includes(type)
      && !entry.url && !entry['@id']) {
      errors.push(`JSON-LD ${type} in block ${index + 1} is missing url/@id`)
    }
    if (['BreadcrumbList', 'ItemList'].includes(type) && !Array.isArray(entry.itemListElement)) {
      errors.push(`JSON-LD ${type} in block ${index + 1} is missing itemListElement`)
    }
  }
  for (const key of ['url', '@id']) {
    if (typeof entry[key] === 'string') validatePublicUrl(entry[key], `JSON-LD ${key}`, errors)
  }
}
