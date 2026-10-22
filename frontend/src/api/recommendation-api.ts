import { recommendationSchema, type Recommendation } from '@/domain/types'
import { requestJson } from './http-client'

/** PPO-selected steps of a stored simulation. Comparison ids are not accepted here (404). */
export function getRecommendation(simulationId: string, signal?: AbortSignal): Promise<Recommendation> {
  return requestJson(`/recommendations/${encodeURIComponent(simulationId)}`, recommendationSchema, { signal })
}
