import { useQuery } from '@tanstack/react-query'
import { getComparison } from '@/api/comparison-api'
import { queryKeys } from '@/api/query-keys'

/** A stored run never changes, so it is cached for the session. */
export function useComparison(id: string | undefined) {
  return useQuery({
    queryKey: queryKeys.comparison(id ?? ''),
    queryFn: ({ signal }) => getComparison(id ?? '', signal),
    enabled: id !== undefined,
    staleTime: Infinity,
  })
}
