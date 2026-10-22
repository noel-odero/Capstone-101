import { afterEach, describe, expect, it, vi } from 'vitest'
import { z } from 'zod'
import { rawFixtures } from '@/test/fixtures/api-fixtures'
import { ApiError } from './api-errors'
import { buildUrl, requestJson } from './http-client'

const schema = z.object({ value: z.number() })

function respond(status: number, body: unknown, contentType = 'application/json') {
  return new Response(typeof body === 'string' ? body : JSON.stringify(body), { status, headers: { 'Content-Type': contentType } })
}

async function failureOf(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise
  } catch (error) {
    if (error instanceof ApiError) {
      return error
    }
    throw error
  }
  throw new Error('Expected the request to fail.')
}

afterEach(() => {
  vi.useRealTimers()
})

describe('buildUrl', () => {
  it('prefixes every path with /api/v1 and honours the base URL', () => {
    expect(buildUrl('/model', undefined, '')).toBe('/api/v1/model')
    expect(buildUrl('/model', undefined, 'https://api.example.org')).toBe('https://api.example.org/api/v1/model')
  })

  it('adds query parameters and skips undefined ones', () => {
    expect(buildUrl('/simulations/recent', { page: 2, pageSize: 10, skipped: undefined }, '')).toBe(
      '/api/v1/simulations/recent?page=2&pageSize=10',
    )
  })
})

describe('requestJson', () => {
  it('parses a successful response with its schema', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond(200, { value: 3 }))
    vi.stubGlobal('fetch', fetchMock)
    await expect(requestJson('/x', schema)).resolves.toEqual({ value: 3 })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/x')
  })

  it('serialises a JSON body for POST and sends no content type without one', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(respond(201, { value: 1 })))
    vi.stubGlobal('fetch', fetchMock)
    await requestJson('/x', schema, { method: 'POST', body: { resistanceProfile: [0, 1, 0, 0, 0, 0, 0] } })
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit
    expect(init.method).toBe('POST')
    expect(init.body).toBe('{"resistanceProfile":[0,1,0,0,0,0,0]}')
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json')

    await requestJson('/y', schema)
    const getInit = fetchMock.mock.calls[1]?.[1] as RequestInit
    expect(getInit.body).toBeUndefined()
    expect((getInit.headers as Record<string, string>)['Content-Type']).toBeUndefined()
  })

  it('maps a 422 problem to a validation error carrying field errors and the correlation id', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respond(422, rawFixtures.problemValidation, 'application/problem+json')))
    const error = await failureOf(requestJson('/x', schema, { method: 'POST', body: {} }))
    expect(error.kind).toBe('validation')
    expect(error.status).toBe(422)
    expect(error.correlationId).toBeTruthy()
    expect(error.fieldErrors['resistanceProfile']?.[0]).toMatch(/7 values/)
  })

  it('does not retry a failed creation request', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond(503, { code: 'database_unavailable', detail: 'down' }, 'application/problem+json'))
    vi.stubGlobal('fetch', fetchMock)
    const error = await failureOf(requestJson('/comparisons', schema, { method: 'POST', body: {} }))
    expect(error.kind).toBe('dependency_unavailable')
    expect(error.code).toBe('database_unavailable')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('reports an unreachable server as a network error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    expect((await failureOf(requestJson('/x', schema))).kind).toBe('network')
  })

  it('reports a malformed body and a schema mismatch as malformed responses, not as success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respond(200, '{not json')))
    expect((await failureOf(requestJson('/x', schema))).kind).toBe('malformed_response')

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respond(200, { value: 'three' })))
    expect((await failureOf(requestJson('/x', schema))).kind).toBe('malformed_response')
  })

  it('uses a generic error when an error response is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respond(500, '<html>boom</html>', 'text/html')))
    const error = await failureOf(requestJson('/x', schema))
    expect(error.kind).toBe('server_error')
    expect(error.message).not.toContain('boom')
  })

  it('accepts a listed non-2xx status as a normal body (the health report on 503)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(respond(503, { value: 9 })))
    await expect(requestJson('/x', schema, { alsoAccept: [503] })).resolves.toEqual({ value: 9 })
  })

  it('reports caller cancellation as an aborted request', async () => {
    const controller = new AbortController()
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init: RequestInit) => new Promise((_resolve, reject) => init.signal?.addEventListener('abort', () => reject(new DOMException('x', 'AbortError'))))),
    )
    const pending = failureOf(requestJson('/x', schema, { signal: controller.signal }))
    controller.abort()
    expect((await pending).kind).toBe('aborted')
  })

  it('stops a request that exceeds its timeout and says so', async () => {
    vi.useFakeTimers()
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init: RequestInit) => new Promise((_resolve, reject) => init.signal?.addEventListener('abort', () => reject(new DOMException('x', 'AbortError'))))),
    )
    const pending = failureOf(requestJson('/x', schema, { timeoutMs: 1000 }))
    await vi.advanceTimersByTimeAsync(1001)
    expect((await pending).kind).toBe('timeout')
  })
})
