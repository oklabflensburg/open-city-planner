export function sanitizeInternalRedirect(value: unknown, fallback = '/') {
  if (typeof value !== 'string') {
    return fallback
  }

  const candidate = value.trim()
  if (!candidate.startsWith('/') || candidate.startsWith('//') || candidate.includes('\\')) {
    return fallback
  }

  try {
    const parsed = new URL(candidate, 'http://internal.local')
    if (parsed.origin !== 'http://internal.local') {
      return fallback
    }
  } catch {
    return fallback
  }

  return candidate
}
