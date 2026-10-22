export class ConfigurationError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ConfigurationError'
  }
}

export interface Environment {
  /** Origin of the public API, or an empty string to call the page's own origin (the Vite proxy in development). */
  apiBaseUrl: string
}

/**
 * Validates `VITE_API_BASE_URL`. Empty means same-origin. Anything else must be an http(s) origin with no path,
 * because every request path already starts with `/api/v1`. The value is public: it is embedded in the bundle.
 */
export function loadEnvironment(raw: { VITE_API_BASE_URL?: string }): Environment {
  const value = (raw.VITE_API_BASE_URL ?? '').trim()
  if (value === '') {
    return { apiBaseUrl: '' }
  }

  let url: URL
  try {
    url = new URL(value)
  } catch {
    throw new ConfigurationError(`VITE_API_BASE_URL must be an absolute http(s) URL or empty, but was "${value}".`)
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new ConfigurationError('VITE_API_BASE_URL must use http or https.')
  }
  if (url.pathname !== '/' || url.search !== '' || url.hash !== '') {
    throw new ConfigurationError('VITE_API_BASE_URL must be an origin only, without a path, query or fragment.')
  }
  if (url.username !== '' || url.password !== '') {
    throw new ConfigurationError('VITE_API_BASE_URL must not contain credentials.')
  }
  return { apiBaseUrl: url.origin }
}

let cached: Environment | undefined

export function getEnvironment(): Environment {
  cached ??= loadEnvironment(import.meta.env)
  return cached
}
