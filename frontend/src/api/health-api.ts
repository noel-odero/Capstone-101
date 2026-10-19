import { healthSchema, type Health } from '@/domain/types'
import { requestJson } from './http-client'

/** An unready backend answers 503 with a full report, which is data here rather than an error. */
export function getHealth(signal?: AbortSignal): Promise<Health> {
  return requestJson('/health', healthSchema, { signal, alsoAccept: [503] })
}

export function getLiveness(signal?: AbortSignal): Promise<Health> {
  return requestJson('/health/live', healthSchema, { signal })
}
