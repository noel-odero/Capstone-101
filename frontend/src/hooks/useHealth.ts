import { useQuery } from '@tanstack/react-query'
import { getHealth } from '@/api/health-api'
import { queryKeys } from '@/api/query-keys'

/** Read once per session and when the window regains focus; there is no polling. */
export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: ({ signal }) => getHealth(signal),
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  })
}
