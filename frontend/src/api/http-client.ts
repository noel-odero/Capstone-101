import type { z } from 'zod'
import { getEnvironment } from '@/config/environment'
import {
  ApiError,
  abortedError,
  errorFromResponse,
  malformedResponseError,
  networkError,
  timeoutError,
} from './api-errors'

export const API_PREFIX = '/api/v1'

/** Reads get a short limit; run creation allows for the scientific service (60 s upstream) plus the database save. */
export const TIMEOUTS = { read: 20_000, create: 90_000 } as const

export type QueryParams = Readonly<Record<string, string | number | undefined>>

let csrfToken: string | null = null
const unauthenticatedListeners = new Set<() => void>()

/** The antiforgery token from `GET /auth/session`, kept in memory only and sent with every state-changing request. */
export function setCsrfToken(token: string | null): void {
  csrfToken = token
}

/** Told when the server answers 401, so the session state can be cleared in one place. Returns an unsubscribe function. */
export function onUnauthenticated(listener: () => void): () => void {
  unauthenticatedListeners.add(listener)
  return () => unauthenticatedListeners.delete(listener)
}

export interface RequestOptions {
  method?: 'GET' | 'POST'
  body?: unknown
  query?: QueryParams
  signal?: AbortSignal | undefined
  timeoutMs?: number
  /** Statuses outside 2xx whose body is still a normal response of the schema (the health report on 503). */
  alsoAccept?: readonly number[]
}

export function buildUrl(path: string, query?: QueryParams, baseUrl = getEnvironment().apiBaseUrl): string {
  const url = `${baseUrl}${API_PREFIX}${path}`
  if (!query) {
    return url
  }
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined) {
      params.set(key, String(value))
    }
  }
  const search = params.toString()
  return search === '' ? url : `${url}?${search}`
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text()
  return text === '' ? undefined : (JSON.parse(text) as unknown)
}

/**
 * The single HTTP boundary to the public .NET API. It never retries: a creation request may have been stored even
 * if the browser did not receive the answer, so repeating it could create a second run.
 */
export async function requestJson<T>(
  path: string,
  schema: z.ZodType<T>,
  options: RequestOptions = {},
): Promise<T> {
  const {
    method = 'GET',
    body,
    query,
    signal,
    timeoutMs = method === 'GET' ? TIMEOUTS.read : TIMEOUTS.create,
    alsoAccept = [],
  } = options

  const controller = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)
  const forwardAbort = () => controller.abort()
  if (signal?.aborted) {
    controller.abort()
  }
  signal?.addEventListener('abort', forwardAbort, { once: true })

  try {
    const response = await fetch(buildUrl(path, query), {
      method,
      signal: controller.signal,
      headers: {
        Accept: 'application/json, application/problem+json',
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...(method !== 'GET' && csrfToken ? { 'X-CSRF-TOKEN': csrfToken } : {}),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })

    const accepted = response.ok || alsoAccept.includes(response.status)
    let payload: unknown
    try {
      payload = await readJson(response)
    } catch (error) {
      if (controller.signal.aborted) {
        throw error
      }
      if (!accepted) {
        throw errorFromResponse(response.status, undefined)
      }
      throw malformedResponseError(error, response.status)
    }

    if (!accepted) {
      throw errorFromResponse(response.status, payload)
    }

    const parsed = schema.safeParse(payload)
    if (!parsed.success) {
      throw malformedResponseError(parsed.error, response.status)
    }
    return parsed.data
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.kind === 'unauthenticated' && path !== '/auth/session') {
        unauthenticatedListeners.forEach((listener) => listener())
      }
      throw error
    }
    if (timedOut) {
      throw timeoutError()
    }
    if (signal?.aborted || (error instanceof DOMException && error.name === 'AbortError')) {
      throw abortedError()
    }
    throw networkError(error)
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', forwardAbort)
  }
}
