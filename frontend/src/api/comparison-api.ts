import { comparisonSchema, type Comparison, type CreateComparisonRequest } from '@/domain/types'
import { requestJson } from './http-client'

/** Stores a new run on every call; callers must not retry it automatically. */
export function createComparison(
  request: CreateComparisonRequest,
  signal?: AbortSignal,
): Promise<Comparison> {
  return requestJson('/comparisons', comparisonSchema, { method: 'POST', body: request, signal })
}

export function getComparison(id: string, signal?: AbortSignal): Promise<Comparison> {
  return requestJson(`/comparisons/${encodeURIComponent(id)}`, comparisonSchema, { signal })
}
