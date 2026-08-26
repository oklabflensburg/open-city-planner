export function referenceApiUrl(baseUrl: string, suffix = '') {
  return `${baseUrl.replace(/\/$/, '')}/modules/reference/items${suffix}`
}
