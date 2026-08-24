const REQUEST_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$/

export function requestIdFor(value?: string) {
  return value && REQUEST_ID_PATTERN.test(value) ? value : crypto.randomUUID()
}

export function routeTemplate(pathname: string) {
  const segments = pathname.split('/').map((segment, index, values) => {
    if (!segment) return segment
    if (/^\d+$/.test(segment) || /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(segment)) return '{id}'
    const parent = values[index - 1]
    if (parent && ['flaechen', 'gebiete'].includes(parent)) return '{slug}'
    if (parent === 'dokumentation' || values[index - 2] === 'dokumentation') return '{slug}'
    return segment
  })
  return segments.join('/') || '/'
}
