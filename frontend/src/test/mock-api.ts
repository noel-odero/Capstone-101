import { vi } from 'vitest'
import { emptyRecentRuns, rawFixtures } from './fixtures/api-fixtures'

export interface MockResponse {
  status?: number
  body?: unknown
  /** Simulates the browser failing to reach the server at all. */
  networkError?: boolean
}

export interface RecordedCall {
  method: string
  path: string
  search: string
  body: unknown
}

type Handler = MockResponse | ((call: RecordedCall) => MockResponse)

/** Routes are keyed `"GET /api/v1/model"`; the query string is ignored when matching. */
export type MockRoutes = Record<string, Handler>

/** Replaces `fetch` for the current test. An unmatched request is answered with 599 so the test fails visibly. */
export function mockFetch(routes: MockRoutes) {
  const calls: RecordedCall[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(
      typeof input === 'string' ? input : input instanceof URL ? input.href : input.url,
      'http://localhost',
    )
    const method = init?.method ?? 'GET'
    const call: RecordedCall = {
      method,
      path: url.pathname,
      search: url.search,
      body: typeof init?.body === 'string' ? (JSON.parse(init.body) as unknown) : undefined,
    }
    calls.push(call)

    const handler = routes[`${method} ${url.pathname}`]
    if (!handler) {
      return new Response(JSON.stringify({ title: `No mock for ${method} ${url.pathname}` }), {
        status: 599,
      })
    }
    const response = typeof handler === 'function' ? handler(call) : handler
    if (response.networkError) {
      throw new TypeError('Failed to fetch')
    }
    return new Response(response.body === undefined ? null : JSON.stringify(response.body), {
      status: response.status ?? 200,
      headers: {
        'Content-Type':
          response.status && response.status >= 400
            ? 'application/problem+json'
            : 'application/json',
      },
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return {
    calls,
    fetchMock,
    callsTo: (key: string) => calls.filter((call) => `${call.method} ${call.path}` === key),
  }
}

/** The read endpoints every page needs, answered with real captured responses. Override per test as needed. */
export function baseRoutes(overrides: MockRoutes = {}): MockRoutes {
  return {
    'GET /api/v1/health': { body: rawFixtures.health },
    'GET /api/v1/model': { body: rawFixtures.model },
    'GET /api/v1/antibiotics': { body: rawFixtures.antibiotics },
    'GET /api/v1/simulations/recent': { body: emptyRecentRuns },
    'GET /api/v1/samples': { body: [] },
    ...overrides,
  }
}
