import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { getRecentRuns } from '@/api/recent-runs-api'
import { queryKeys } from '@/api/query-keys'

export const RECENT_RUNS_PAGE_SIZE = 10

export function useRecentRuns(page: number, pageSize: number = RECENT_RUNS_PAGE_SIZE) {
  return useQuery({
    queryKey: queryKeys.recentRuns(page, pageSize),
    queryFn: ({ signal }) => getRecentRuns(page, pageSize, signal),
    staleTime: 15_000,
    placeholderData: keepPreviousData,
  })
}
