import { describe, expect, it } from 'vitest'
import { queryKeys } from './query-keys'
import { createQueryClient, shouldRetryQuery } from '@/app/query-client'
import { ApiError } from './api-errors'
import { loadEnvironment, ConfigurationError } from '@/config/environment'

describe('query keys', () => {
  it('derives a stable key from the profile code, so equal profiles share a cache entry', () => {
    expect(queryKeys.profileValidation([0, 1, 0, 0, 0, 0, 0])).toEqual(queryKeys.profileValidation([0, 1, 0, 0, 0, 0, 0]))
    expect(queryKeys.profileValidation([0, 1, 0, 0, 0, 0, 0])).not.toEqual(queryKeys.profileValidation([1, 1, 0, 0, 0, 0, 0]))
  })

  it('keeps run kinds apart even for the same id', () => {
    expect(queryKeys.simulation('a')).not.toEqual(queryKeys.comparison('a'))
    expect(queryKeys.recommendation('a')).not.toEqual(queryKeys.simulation('a'))
  })

  it('nests every recent-runs page under one root so a single invalidation covers them all', () => {
    const root = queryKeys.recentRunsRoot
    expect(queryKeys.recentRuns(2, 10).slice(0, root.length)).toEqual([...root])
  })
})

describe('query client defaults', () => {
  it('never retries mutations, because creating a run stores it', () => {
    expect(createQueryClient().getDefaultOptions().mutations?.retry).toBe(false)
  })

  it('retries a read only for transient failures and only a couple of times', () => {
    expect(shouldRetryQuery(0, new ApiError({ kind: 'network', message: 'x' }))).toBe(true)
    expect(shouldRetryQuery(2, new ApiError({ kind: 'network', message: 'x' }))).toBe(false)
    expect(shouldRetryQuery(0, new ApiError({ kind: 'not_found', message: 'x' }))).toBe(false)
    expect(shouldRetryQuery(0, new ApiError({ kind: 'validation', message: 'x' }))).toBe(false)
    expect(shouldRetryQuery(0, new Error('unexpected'))).toBe(false)
  })
})

describe('environment configuration', () => {
  it('defaults to the same origin', () => {
    expect(loadEnvironment({})).toEqual({ apiBaseUrl: '' })
    expect(loadEnvironment({ VITE_API_BASE_URL: '  ' })).toEqual({ apiBaseUrl: '' })
  })

  it('accepts an http(s) origin and drops a trailing slash', () => {
    expect(loadEnvironment({ VITE_API_BASE_URL: 'http://localhost:5080/' })).toEqual({ apiBaseUrl: 'http://localhost:5080' })
    expect(loadEnvironment({ VITE_API_BASE_URL: 'https://api.example.org' }).apiBaseUrl).toBe('https://api.example.org')
  })

  it.each(['localhost:5080', 'ftp://example.org', 'http://example.org/api', 'http://user:pw@example.org', 'http://example.org?x=1', 'not a url'])(
    'fails clearly for %s',
    (value) => {
      expect(() => loadEnvironment({ VITE_API_BASE_URL: value })).toThrow(ConfigurationError)
    },
  )
})
