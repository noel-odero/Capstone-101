import { recentRunsSchema, type RecentRuns } from '@/domain/types'
import { requestJson } from './http-client'

/** Simulations and comparisons together, newest first. The server caps `pageSize` at 50. */
export function getRecentRuns(
  page: number,
  pageSize: number,
  signal?: AbortSignal,
): Promise<RecentRuns> {
  return requestJson('/simulations/recent', recentRunsSchema, { query: { page, pageSize }, signal })
}
