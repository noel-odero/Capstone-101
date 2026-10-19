import { describe, expect, it } from 'vitest'
import { rawFixtures } from '@/test/fixtures/api-fixtures'
import {
  ApiError,
  abortedError,
  errorFromResponse,
  errorTitle,
  isApiError,
  malformedResponseError,
  networkError,
  normalizeError,
  parseProblemDetails,
  timeoutError,
} from './api-errors'

describe('error normalisation', () => {
  it.each([
    [404, 'not_found'],
    [415, 'unsupported_media_type'],
    [422, 'validation'],
    [502, 'upstream_failure'],
    [503, 'dependency_unavailable'],
    [500, 'server_error'],
    [504, 'server_error'],
    [405, 'client_error'],
  ])('maps HTTP %i to %s', (status, kind) => {
    expect(errorFromResponse(status, undefined).kind).toBe(kind)
  })

  it('keeps the backend code, correlation id and field errors from a validation problem', () => {
    const error = errorFromResponse(422, rawFixtures.problemValidation)
    expect(error.kind).toBe('validation')
    expect(error.code).toBe('validation_failed')
    expect(error.correlationId).toBeTruthy()
    expect(error.fieldErrors['resistanceProfile']).toEqual(['A resistance profile must have exactly 7 values.'])
  })

  it('shows the backend detail for a not-found problem but never a raw body', () => {
    const error = errorFromResponse(404, rawFixtures.problemRecommendationNotFound)
    expect(error.message).toBe('No PPO recommendations exist for this simulation.')
    expect(error.code).toBe('recommendation_not_found')
  })

  it('falls back to generic text for an unreadable body or an oversized detail', () => {
    expect(errorFromResponse(500, '<html>stack trace</html>').message).toMatch(/unexpected problem/i)
    expect(errorFromResponse(503, { detail: 'x'.repeat(2000) }).message).toMatch(/unavailable/i)
    expect(parseProblemDetails('nonsense')).toBeUndefined()
  })

  it('marks only transient read failures as retryable and cancellation as not an error to show', () => {
    expect(networkError(new Error('x')).isTransient).toBe(true)
    expect(timeoutError().isTransient).toBe(true)
    expect(errorFromResponse(503, undefined).isTransient).toBe(true)
    expect(errorFromResponse(422, undefined).isTransient).toBe(false)
    expect(errorFromResponse(404, undefined).isTransient).toBe(false)
    expect(abortedError().isCancellation).toBe(true)
    expect(timeoutError().isCancellation).toBe(false)
  })

  it('has distinct user-safe messages for network, timeout and malformed responses', () => {
    const messages = [networkError(null), timeoutError(), malformedResponseError(null)].map((error) => error.message)
    expect(new Set(messages).size).toBe(3)
    for (const message of messages) {
      expect(message).not.toMatch(/at \w+\.|Error:|stack/i)
    }
  })

  it('turns anything thrown into an ApiError', () => {
    expect(isApiError(normalizeError(new Error('boom')))).toBe(true)
    expect(normalizeError(new Error('boom')).kind).toBe('server_error')
    expect(normalizeError(new DOMException('aborted', 'AbortError')).kind).toBe('aborted')
    const existing = new ApiError({ kind: 'not_found', message: 'gone' })
    expect(normalizeError(existing)).toBe(existing)
  })

  it('gives each kind a readable title', () => {
    expect(errorTitle(networkError(null))).toBe('Cannot reach the API')
    expect(errorTitle(errorFromResponse(503, undefined))).toBe('A backend service is unavailable')
    expect(errorTitle(errorFromResponse(500, { code: 'persistence_failed' }))).toBe('Persistence failed')
  })
})
